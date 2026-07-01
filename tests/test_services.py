"""
tests/test_services.py

Unit tests for calculate_streak() and get_reading_history().

Uses an in-memory SQLite database so tests are isolated and fast.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app import create_app
from extensions import db
from models import User, Book, ReadingEvent
from services import stats_service, reading_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a fresh app with an in-memory database for each test."""
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username="alice", email="alice@test.com"):
    user = User(username=username, email=email)
    db.session.add(user)
    db.session.flush()
    return user


def make_book(user_id, title="A Book", pages=200):
    book = Book(title=title, author="Author", pages=pages, added_by=user_id)
    db.session.add(book)
    db.session.flush()
    return book


def make_finished_event(user_id, book_id, finished_at):
    """Create a completed ReadingEvent (started 7 days before finished)."""
    event = ReadingEvent(
        user_id=user_id,
        book_id=book_id,
        started_at=finished_at - timedelta(days=7),
        finished_at=finished_at,
    )
    db.session.add(event)
    db.session.flush()
    return event


def make_in_progress_event(user_id, book_id, started_at):
    """Create an in-progress ReadingEvent (no finished_at)."""
    event = ReadingEvent(
        user_id=user_id,
        book_id=book_id,
        started_at=started_at,
        finished_at=None,
    )
    db.session.add(event)
    db.session.flush()
    return event


# ---------------------------------------------------------------------------
# calculate_streak() tests
# ---------------------------------------------------------------------------

class TestCalculateStreak:

    def test_three_consecutive_days_returns_three(self, app):
        """Books finished on 3 consecutive days should yield streak = 3."""
        with app.app_context():
            now = datetime.now(timezone.utc)
            user = make_user()
            b1 = make_book(user.id, "Book A")
            b2 = make_book(user.id, "Book B")
            b3 = make_book(user.id, "Book C")

            make_finished_event(user.id, b1.id, now)
            make_finished_event(user.id, b2.id, now - timedelta(days=1))
            make_finished_event(user.id, b3.id, now - timedelta(days=2))
            db.session.commit()

            assert stats_service.calculate_streak(user.id) == 3

    def test_no_history_returns_zero(self, app):
        """User with no finished books should have streak = 0."""
        with app.app_context():
            user = make_user("newuser", "new@test.com")
            db.session.commit()

            assert stats_service.calculate_streak(user.id) == 0

    def test_gap_in_streak_breaks_it(self, app):
        """A one-day gap should break the streak at the gap."""
        with app.app_context():
            now = datetime.now(timezone.utc)
            user = make_user("gapuser", "gap@test.com")
            b1 = make_book(user.id, "Day 0")
            b2 = make_book(user.id, "Day 1")
            b3 = make_book(user.id, "Day 3 (gap)")  # skipped day 2

            make_finished_event(user.id, b1.id, now)
            make_finished_event(user.id, b2.id, now - timedelta(days=1))
            make_finished_event(user.id, b3.id, now - timedelta(days=3))
            db.session.commit()

            # streak is 2 (today + yesterday), stops at the gap
            assert stats_service.calculate_streak(user.id) == 2

    def test_stale_history_returns_zero(self, app):
        """Last finish more than 1 day ago should give streak = 0."""
        with app.app_context():
            now = datetime.now(timezone.utc)
            user = make_user("staleuser", "stale@test.com")
            b1 = make_book(user.id, "Old Book")

            make_finished_event(user.id, b1.id, now - timedelta(days=5))
            db.session.commit()

            assert stats_service.calculate_streak(user.id) == 0

    def test_in_progress_books_not_counted(self, app):
        """Books started but not finished must not contribute to the streak."""
        with app.app_context():
            now = datetime.now(timezone.utc)
            user = make_user("inprogress", "inprog@test.com")
            b1 = make_book(user.id, "Finished")
            b2 = make_book(user.id, "In Progress")

            make_finished_event(user.id, b1.id, now)
            make_in_progress_event(user.id, b2.id, now - timedelta(days=1))
            db.session.commit()

            # Only one day has a finished book
            assert stats_service.calculate_streak(user.id) == 1


# ---------------------------------------------------------------------------
# get_reading_history() tests
# ---------------------------------------------------------------------------

class TestGetReadingHistory:

    def test_ordered_by_finished_at_descending(self, app):
        """History must return books most-recently-finished first."""
        with app.app_context():
            now = datetime.now(timezone.utc)
            user = make_user("orderuser", "order@test.com")

            # Book started first but finished last (mirrors the seed data scenario)
            b_early_start = make_book(user.id, "Early Start Late Finish", pages=300)
            b_late_start  = make_book(user.id, "Late Start Early Finish", pages=150)

            make_finished_event(user.id, b_early_start.id,
                                finished_at=now - timedelta(hours=2))   # most recent
            make_finished_event(user.id, b_late_start.id,
                                finished_at=now - timedelta(days=1))    # older
            db.session.commit()

            history = reading_service.get_reading_history(user.id)

            assert len(history) == 2
            assert history[0].book_id == b_early_start.id   # finished most recently
            assert history[1].book_id == b_late_start.id
            assert history[0].finished_at > history[1].finished_at

    def test_excludes_in_progress_books(self, app):
        """Books with finished_at=None must not appear in history."""
        with app.app_context():
            now = datetime.now(timezone.utc)
            user = make_user("filteruser", "filter@test.com")
            b_done = make_book(user.id, "Done")
            b_wip  = make_book(user.id, "Still Reading")

            make_finished_event(user.id, b_done.id, now - timedelta(days=1))
            make_in_progress_event(user.id, b_wip.id, now - timedelta(days=3))
            db.session.commit()

            history = reading_service.get_reading_history(user.id)

            assert len(history) == 1
            assert history[0].book_id == b_done.id

    def test_empty_history_for_new_user(self, app):
        """A user who has never finished a book gets an empty list."""
        with app.app_context():
            user = make_user("freshuser", "fresh@test.com")
            db.session.commit()

            assert reading_service.get_reading_history(user.id) == []


# ---------------------------------------------------------------------------
# books_this_month() — UTC consistency
# ---------------------------------------------------------------------------

class TestBooksThisMonth:

    def test_counts_books_finished_in_current_utc_month(self, app):
        """Only books whose finished_at falls in the current UTC month are counted."""
        with app.app_context():
            now_utc = datetime.now(timezone.utc)
            user = make_user("monthuser", "month@test.com")
            b_this_month = make_book(user.id, "This Month")
            b_last_month = make_book(user.id, "Last Month")

            # finished today (this month in UTC)
            make_finished_event(user.id, b_this_month.id, now_utc - timedelta(hours=1))
            # finished 35 days ago (definitely last month in UTC)
            make_finished_event(user.id, b_last_month.id, now_utc - timedelta(days=35))
            db.session.commit()

            assert stats_service.books_this_month(user.id) == 1

    def test_zero_when_no_books_this_month(self, app):
        """Returns 0 when all finished books are from previous months."""
        with app.app_context():
            now_utc = datetime.now(timezone.utc)
            user = make_user("oldmonth", "old@test.com")
            b = make_book(user.id, "Old Book")
            make_finished_event(user.id, b.id, now_utc - timedelta(days=40))
            db.session.commit()

            assert stats_service.books_this_month(user.id) == 0


# ---------------------------------------------------------------------------
# add_book() — pages validation
# ---------------------------------------------------------------------------

class TestAddBook:

    def test_zero_pages_raises_value_error(self, app):
        """Adding a book with pages=0 must raise ValueError."""
        with app.app_context():
            user = make_user("pageuser", "page@test.com")
            db.session.commit()

            with pytest.raises(ValueError, match="pages must be a positive integer"):
                reading_service.add_book(
                    title="Empty Book", author="Author", pages=0,
                    genre="test", user_id=user.id
                )

    def test_negative_pages_raises_value_error(self, app):
        """Adding a book with negative pages must raise ValueError."""
        with app.app_context():
            user = make_user("negpage", "neg@test.com")
            db.session.commit()

            with pytest.raises(ValueError, match="pages must be a positive integer"):
                reading_service.add_book(
                    title="Negative Book", author="Author", pages=-5,
                    genre="test", user_id=user.id
                )

    def test_valid_pages_creates_book(self, app):
        """Adding a book with valid pages succeeds."""
        with app.app_context():
            user = make_user("validpage", "valid@test.com")
            db.session.commit()

            book = reading_service.add_book(
                title="Real Book", author="Author", pages=300,
                genre="fiction", user_id=user.id
            )
            assert book.pages == 300
