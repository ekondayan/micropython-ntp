import unittest
from ..src import ntp


class TestDayFromWeekAndWeekday(unittest.TestCase):
    """Unit tests for function day_from_week_and_weekday(cls, year, month, week, weekday)"""

    test_dates = [
        ((2013, ntp.Ntp.MONTH_MAR, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_MON), 4),
        ((2013, ntp.Ntp.MONTH_MAR, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_SUN), 31),
        ((2013, ntp.Ntp.MONTH_OCT, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_MON), 7),
        ((2013, ntp.Ntp.MONTH_OCT, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_SUN), 27),

        ((2015, ntp.Ntp.MONTH_APR, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_THU), 2),
        ((2015, ntp.Ntp.MONTH_APR, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_SUN), 26),
        ((2015, ntp.Ntp.MONTH_NOV, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_SUN), 1),
        ((2015, ntp.Ntp.MONTH_NOV, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_MON), 30),

        ((2017, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_WED), 1),
        ((2017, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_SUN), 5),
        ((2017, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_TUE), 7),
        ((2017, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_SUN), 26),
        ((2017, ntp.Ntp.MONTH_SEP, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_SAT), 2),
        ((2017, ntp.Ntp.MONTH_SEP, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_SUN), 24),
        ((2017, ntp.Ntp.MONTH_SEP, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_SAT), 30),

        ((2020, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_SAT), 1),
        ((2020, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_TUE), 4),
        ((2020, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_FRI), 7),
        ((2020, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_FRI), 28),
        ((2020, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_SAT), 29),
        ((2020, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_SUN), 23),
        ((2020, ntp.Ntp.MONTH_OCT, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_FRI), 30),
        ((2020, ntp.Ntp.MONTH_OCT, ntp.Ntp.WEEK_LAST, ntp.Ntp.WEEKDAY_SUN), 25),
        ((2020, ntp.Ntp.MONTH_OCT, ntp.Ntp.WEEK_SECOND, ntp.Ntp.WEEKDAY_TUE), 6),

        ((2022, ntp.Ntp.MONTH_JAN, ntp.Ntp.WEEK_FIRST, ntp.Ntp.WEEKDAY_MON), 3),
        ((2022, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_FIFTH, ntp.Ntp.WEEKDAY_TUE), 22),
        ((2024, ntp.Ntp.MONTH_FEB, ntp.Ntp.WEEK_FIFTH, ntp.Ntp.WEEKDAY_THU), 29),
    ]

    def test_valid_inputs_within_boundary(self):
        errors = []
        for date in self.test_dates:
            try:
                result = ntp.Ntp.day_from_week_and_weekday(*date[0])
            except:
                continue

            if result != date[1]:
                errors.append(f"Expected {date[1]} for sample ({date[0]}), but got {result}.")

        # Raise an assertion with all collected error messages
        self.assertTrue(not errors, "\n".join(errors))

    def test_invalid_month(self):
        with self.assertRaises(ValueError):
            ntp.Ntp.day_from_week_and_weekday(2022, 13, 1, 1)

    def test_invalid_week(self):
        with self.assertRaises(ValueError):
            ntp.Ntp.day_from_week_and_weekday(2022, 1, 0, 1)

    def test_invalid_weekday(self):
        with self.assertRaises(ValueError):
            ntp.Ntp.day_from_week_and_weekday(2022, 1, 1, 8)


# Run the tests
unittest.TextTestRunner().run(unittest.TestLoader().loadTestsFromTestCase(TestDayFromWeekAndWeekday))
