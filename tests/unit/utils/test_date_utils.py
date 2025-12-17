"""Unit tests for date_utils."""

from datetime import datetime, timedelta, timezone

import pytest

from lib.shared.local_assistant_shared.utils.date_utils import (
    calculate_days_until,
    format_relative_date,
    is_overdue,
    parse_flexible_date,
)


def test_parse_flexible_date_iso():
    """Test parsing ISO 8601 date format."""
    dt = parse_flexible_date("2024-02-28")

    assert dt.year == 2024
    assert dt.month == 2
    assert dt.day == 28
    assert dt.tzinfo == timezone.utc


def test_parse_flexible_date_iso_with_time():
    """Test parsing ISO 8601 datetime format."""
    dt = parse_flexible_date("2024-02-28T10:30:00Z")

    assert dt.year == 2024
    assert dt.month == 2
    assert dt.day == 28
    assert dt.hour == 10
    assert dt.minute == 30


def test_parse_flexible_date_us_format():
    """Test parsing US date format."""
    dt = parse_flexible_date("02/28/2024")

    assert dt.year == 2024
    assert dt.month == 2
    assert dt.day == 28


def test_parse_flexible_date_text_format():
    """Test parsing text date format."""
    dt = parse_flexible_date("Feb 28, 2024")

    assert dt.year == 2024
    assert dt.month == 2
    assert dt.day == 28


def test_parse_flexible_date_relative_today():
    """Test parsing relative date 'today'."""
    dt = parse_flexible_date("today")
    now = datetime.now(timezone.utc)

    assert dt.year == now.year
    assert dt.month == now.month
    assert dt.day == now.day
    assert dt.hour == 0
    assert dt.minute == 0


def test_parse_flexible_date_relative_tomorrow():
    """Test parsing relative date 'tomorrow'."""
    dt = parse_flexible_date("tomorrow")
    expected = datetime.now(timezone.utc) + timedelta(days=1)

    assert dt.year == expected.year
    assert dt.month == expected.month
    assert dt.day == expected.day


def test_parse_flexible_date_relative_yesterday():
    """Test parsing relative date 'yesterday'."""
    dt = parse_flexible_date("yesterday")
    expected = datetime.now(timezone.utc) - timedelta(days=1)

    assert dt.year == expected.year
    assert dt.month == expected.month
    assert dt.day == expected.day


def test_parse_flexible_date_invalid():
    """Test parsing invalid date format."""
    with pytest.raises(ValueError, match="Unable to parse date string"):
        parse_flexible_date("not a date")


def test_format_relative_date_today():
    """Test formatting date as 'today'."""
    now = datetime.now(timezone.utc)
    result = format_relative_date(now, now)

    assert result == "today"


def test_format_relative_date_tomorrow():
    """Test formatting date as 'tomorrow'."""
    now = datetime.now(timezone.utc)
    tomorrow = now + timedelta(days=1)
    result = format_relative_date(tomorrow, now)

    assert result == "tomorrow"


def test_format_relative_date_yesterday():
    """Test formatting date as 'yesterday'."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    result = format_relative_date(yesterday, now)

    assert result == "yesterday"


def test_format_relative_date_future_days():
    """Test formatting future dates in days."""
    now = datetime.now(timezone.utc)
    in_3_days = now + timedelta(days=3)
    result = format_relative_date(in_3_days, now)

    assert result == "in 3 days"


def test_format_relative_date_past_days():
    """Test formatting past dates in days."""
    now = datetime.now(timezone.utc)
    three_days_ago = now - timedelta(days=3)
    result = format_relative_date(three_days_ago, now)

    assert result == "3 days ago"


def test_format_relative_date_future_weeks():
    """Test formatting future dates in weeks."""
    now = datetime.now(timezone.utc)
    in_2_weeks = now + timedelta(days=14)
    result = format_relative_date(in_2_weeks, now)

    assert result == "in 2 weeks"


def test_format_relative_date_past_weeks():
    """Test formatting past dates in weeks."""
    now = datetime.now(timezone.utc)
    two_weeks_ago = now - timedelta(days=14)
    result = format_relative_date(two_weeks_ago, now)

    assert result == "2 weeks ago"


def test_format_relative_date_future_months():
    """Test formatting future dates in months."""
    now = datetime.now(timezone.utc)
    in_2_months = now + timedelta(days=60)
    result = format_relative_date(in_2_months, now)

    assert result == "in 2 months"


def test_format_relative_date_past_months():
    """Test formatting past dates in months."""
    now = datetime.now(timezone.utc)
    two_months_ago = now - timedelta(days=60)
    result = format_relative_date(two_months_ago, now)

    assert result == "2 months ago"


def test_calculate_days_until_future():
    """Test calculating days until future date."""
    now = datetime.now(timezone.utc)
    in_7_days = now + timedelta(days=7)
    days = calculate_days_until(in_7_days, now)

    assert days == 7


def test_calculate_days_until_past():
    """Test calculating days until past date."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    days = calculate_days_until(seven_days_ago, now)

    assert days == -7


def test_calculate_days_until_today():
    """Test calculating days until today."""
    now = datetime.now(timezone.utc)
    days = calculate_days_until(now, now)

    assert days == 0


def test_is_overdue_past_date():
    """Test is_overdue with past date."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    assert is_overdue(yesterday, now) is True


def test_is_overdue_future_date():
    """Test is_overdue with future date."""
    now = datetime.now(timezone.utc)
    tomorrow = now + timedelta(days=1)

    assert is_overdue(tomorrow, now) is False


def test_is_overdue_today():
    """Test is_overdue with today."""
    now = datetime.now(timezone.utc)

    assert is_overdue(now, now) is False
