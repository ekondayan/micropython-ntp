try:
    import usocket as socket
except ImportError:
    import socket

try:
    import ustruct as struct
except ImportError:
    import struct

try:
    import utime as time
except ImportError:
    import time

try:
    import ure as re
except ImportError:
    import re

import machine


class Ntp:
    EPOCH_1900 = 0
    EPOCH_1970 = 1
    EPOCH_2000 = 2

    DST_MONTH_JAN = 1
    DST_MONTH_FEB = 2
    DST_MONTH_MAR = 3
    DST_MONTH_APR = 4
    DST_MONTH_MAY = 5
    DST_MONTH_JUN = 6
    DST_MONTH_JUL = 7
    DST_MONTH_AUG = 8
    DST_MONTH_SEP = 9
    DST_MONTH_OCT = 10
    DST_MONTH_NOV = 11
    DST_MONTH_DEC = 12

    DST_WEEK_FIRST = 1
    DST_WEEK_SECOND = 2
    DST_WEEK_THIRD = 3
    DST_WEEK_FORTH = 4
    DST_WEEK_LAST = 5

    DST_DOW_MON = 1
    DST_DOW_TUE = 2
    DST_DOW_WED = 3
    DST_DOW_THU = 4
    DST_DOW_FRI = 5
    DST_DOW_SAT = 6
    DST_DOW_SUN = 7

    _NTP_DELTA_1900_1970 = 2208988800  # Seconds between 1900 and 1970
    _NTP_DELTA_1900_2000 = 3155673600  # Seconds between 1900 and 2000
    _NTP_DELTA_1970_2000 = 946684800   # Seconds between 1970 and 2000 = _NTP_DELTA_1900_2000 - _NTP_DELTA_1900_1970

    _logger = print
    _rtc = machine.RTC()
    _hosts: list = []
    _timezone: int = 0
    _rtc_last_sync: int = 0
    _drift_last_compensate: int = 0
    _drift_last_calculate: int = 0
    _ppm_drift: float = 0.0
    _ntp_timeout_s: int = 1

    # (month, week, day of week, hour)
    _dst_start: tuple = ()
    # (month, week, day of week, hour)
    _dst_end: tuple = ()
    _dst_bias: int = 0

    @classmethod
    def set_dst(cls, start: tuple, end: tuple, bias: int):
        """

        :param start:
        :param end:
        :param bias:
        """
        cls.set_dst_start(start[0], start[1], start[2], start[3])
        cls.set_dst_end(end[0], end[1], end[2], end[3])
        cls.set_dst_time_bias(bias)

    @classmethod
    def set_dst_start(cls, month: int, week: int, dow: int, hour: int):
        """

        :param month:
        :param week:
        :param dow:
        :param hour:
        """
        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError("Invalid parameter: month must be a integer between 1 and 12")
        elif not isinstance(week, int) or not 1 <= week <= 5:
            raise ValueError("Invalid parameter: week must be a integer between 1 and 5")
        elif not isinstance(dow, int) or not 1 <= week <= 7:
            raise ValueError("Invalid parameter: dow must be a integer between 1 and 7")
        elif not isinstance(hour, int) or not 0 <= week <= 23:
            raise ValueError("Invalid parameter: hour must be a integer between 0 and 23")

        cls._dst_start = (month, week, dow, hour)

    @classmethod
    def get_dst_start(cls):
        """

        :return:
        """
        return tuple(cls._dst_start)

    @classmethod
    def set_dst_end(cls, month: int, week: int, dow: int, hour: int):
        """

        :param month:
        :param week:
        :param dow:
        :param hour:
        """
        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError("Invalid parameter: month must be a integer between 1 and 12")
        elif not isinstance(week, int) or not 1 <= week <= 5:
            raise ValueError("Invalid parameter: week must be a integer between 1 and 5")
        elif not isinstance(dow, int) or not 1 <= week <= 7:
            raise ValueError("Invalid parameter: dow must be a integer between 1 and 7")
        elif not isinstance(hour, int) or not 0 <= week <= 23:
            raise ValueError("Invalid parameter: hour must be a integer between 0 and 23")

        cls._dst_end = (month, week, dow, hour)

    @classmethod
    def get_dst_end(cls):
        """

        :return:
        """
        return tuple(cls._dst_end)

    @classmethod
    def set_dst_time_bias(cls, bias: int):
        """

        :param bias:
        """
        if not isinstance(bias, int) or bias not in (30, 60, 90, 120):
            raise ValueError("Invalid parameter: time bias represents minutes offset and must be either 30, 60, 90 or 120")

        cls._dst_bias = bias

    @classmethod
    def get_dst_time_bias(cls):
        """

        :return:
        """
        return cls._dst_bias

    @classmethod
    def dst(cls):
        """
        Calculate if DST is currently present and return the bias.
        :return: Calculated DST bias
        """

        # When DST is disabled, return 0
        if not cls._dst_start or not cls._dst_end:
            return 0

        date = time.localtime()
        year = date[0]
        month = date[1]
        day = date[2]

        if cls._dst_start[0] < month < cls._dst_end[0]:
            return cls._dst_bias
        elif month < cls._dst_start[0] or cls._dst_end[0] < month:
            return 0
        elif cls._dst_start[0] == month:
            # Switch time in hours since the beginning of the month
            switch_hour = cls.day_from_week_and_weekday(year, month, cls._dst_start[1], cls._dst_start[2]) * 24 + cls._dst_start[3]
            if (day * 24 + date[3]) >= switch_hour:
                return cls._dst_bias
        else:
            # Switch time in hours since the beginning of the month
            switch_hour = cls.day_from_week_and_weekday(year, month, cls._dst_end[1], cls._dst_end[2]) * 24 + cls._dst_end[3]
            if (day * 24 + date[3]) < switch_hour:
                return cls._dst_bias

        return 0

    @classmethod
    def set_logger(cls, callback = None):
        """

        :param callback:
        """
        if callback is None or callable(callback):
            cls._logger = callback
        else:
            raise Exception('Callback parameter must be a callable object or None to set it to print()')

    @classmethod
    def set_ntp_timeout(cls, timeout_s: int = 1):
        """

        :param timeout_s:
        """
        if not instance(timeout_s, int):
            raise Exception('Timeout parameter represents seconds in integer form')

        cls._ntp_timeout_s = timeout_s

    @classmethod
    def ntp_timeout(cls):
        """

        :return:
        """
        return cls._ntp_timeout_s

    @classmethod
    def hosts(cls):
        """

        :return:
        """
        return tuple(cls._hosts)

    @classmethod
    def set_hosts(cls, value: list):
        """

        :param value:
        """
        cls._hosts.clear()

        for host in value:
            if Ntp._validate_hostname(host):
                cls._hosts.append(host)

    @classmethod
    def timezone(cls):
        """

        :return:
        """
        return cls._timezone // 3600, (cls._timezone % 3600) // 60

    @classmethod
    def set_timezone(cls, hour: int, minute: int = 0):
        """

        :param hour:
        :param minute:
        """
        if (
                (minute == 0 and not (-12 <= hour <= 12)) or
                (minute == 30 and hour not in (-9, -3, 3, 4, 5, 6, 9, 10)) or
                (minute == 45 and hour not in (5, 8, 12))
        ):
            raise Exception('Timezone is invalid')

        cls._timezone = hour * 3600 + minute * 60

    @classmethod
    def time_s(cls, epoch: int = None):
        """

        :param epoch:
        :return:
        """
        return cls.time_us(epoch) // 1000000

    @classmethod
    def time_ms(cls, epoch: int = None):
        """

        :param epoch:
        :return:
        """
        return cls.time_us(epoch) // 1000

    @classmethod
    def time_us(cls, epoch: int = None):
        """

        :param epoch:
        :return:
        """
        epoch = cls._select_epoch(epoch, (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0))

        # Do not take the value when on the verge of the next second
        # This is required to ensure that the sec and usec will be read within the boundaries of one second
        us = cls._rtc.datetime()[7]
        if us >= 995000:
            time.sleep_us(100000 - us)

        return (time.time() + epoch + cls._timezone + cls.dst()) * 1000000 + cls._rtc.datetime()[7]

    @classmethod
    def network_time(cls, epoch = None):
        """

        :param epoch:
        :return:
        """
        if not any(cls._hosts):
            raise Exception('There are no valid Hostnames/IPs set for the time server')

        epoch = cls._select_epoch(epoch, (0, cls._NTP_DELTA_1900_1970, cls._NTP_DELTA_1900_2000))
        query = bytearray(48)
        query[0] = 0x1B

        for host in cls._hosts:
            s = None
            try:
                host_addr = socket.getaddrinfo(host, 123)[0][-1]
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(cls._ntp_timeout_s)
                s.sendto(query, host_addr)
                timestamp = time.ticks_us()
                msg = s.recv(48)
            except Exception as e:
                cls._log('(NTP) Network error: Host({}) Error({})'.format(host, str(e)))
                continue
            finally:
                if s is not None:
                    s.close()

            sec, nano = struct.unpack('!II', msg[40:48])
            if sec < epoch:
                cls._log('(NTP) Invalid packet: Host({})'.format(host))
                continue

            sec -= epoch
            micro = (nano * 1000000) >> 32
            return sec * 1000000 + micro, timestamp

        raise Exception('''Can't connect to any of the NTP servers''')

    @classmethod
    def rtc_sync(cls):
        """

        """
        ntp_reading = cls.network_time(cls.EPOCH_2000)

        # Negate the execution time of all the instructions up to this point
        ntp_us = ntp_reading[0] + (time.ticks_us() - ntp_reading[1])
        lt = time.localtime(ntp_us // 1000000)
        cls._rtc.datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], ntp_us % 1000000))
        cls._rtc_last_sync = ntp_us

    @classmethod
    def rtc_last_sync(cls, epoch: int = None):
        """

        :param epoch:
        :return:
        """
        epoch = cls._select_epoch(epoch, (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0))
        return cls._rtc_last_sync + epoch * 1000000

    @classmethod
    def drift_calculate(cls):
        """

        :return:
        """
        ntp_reading = cls.network_time(cls.EPOCH_2000)

        rtc_us = cls.time_us(Ntp.EPOCH_2000)
        # Negate the execution time of all the instructions up to this point
        ntp_us = ntp_reading[0] + (time.ticks_us() - ntp_reading[1])

        rtc_sync_delta = ntp_us - max(cls._rtc_last_sync, cls._drift_last_compensate)
        rtc_ntp_delta = rtc_us - ntp_us

        cls._ppm_drift = (rtc_ntp_delta / rtc_sync_delta) * 1000000

        cls._drift_last_calculate = ntp_us

        return cls._ppm_drift, rtc_ntp_delta

    @classmethod
    def drift_last_compensate(cls, epoch: int = None):
        """

        :param epoch:
        :return:
        """
        epoch = cls._select_epoch(epoch, (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0))
        return cls._drift_last_compensate + epoch * 1000000

    @classmethod
    def drift_last_calculate(cls, epoch: int = None):
        """

        :param epoch:
        :return:
        """
        epoch = cls._select_epoch(epoch, (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0))
        return cls._drift_last_calculate + epoch * 1000000

    @classmethod
    def drift_ppm(cls):
        """

        :return:
        """
        return cls._ppm_drift

    @classmethod
    def set_drift_ppm(cls, ppm: float):
        """

        :param ppm:
        """
        if not isinstance(ppm, (float, int)):
            raise Exception('ppm parameter must be float or int')
        cls._ppm_drift = float(ppm)

    @classmethod
    def drift_us(cls, ppm_drift: float = None):
        """

        :param ppm_drift:
        :return:
        """
        if cls._rtc_last_sync == 0 and cls._drift_last_compensate == 0:
            return 0

        if ppm_drift is None:
            ppm_drift = cls._ppm_drift

        delta_time_rtc = cls.time_us(cls.EPOCH_2000) - max(cls._rtc_last_sync, cls._drift_last_compensate)
        delta_time_real = (1000000 * delta_time_rtc) // (1000000 + ppm_drift)

        return delta_time_rtc - delta_time_real

    @classmethod
    def drift_compensate(cls, compensate_us: int):
        """

        :param compensate_us:
        """
        rtc_us = cls.time_us(Ntp.EPOCH_2000)
        rtc_us += compensate_us
        lt = time.localtime(rtc_us // 1000000)
        cls._rtc.datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], rtc_us % 1000000))
        cls._drift_last_compensate = rtc_us

    @classmethod
    def weekday(cls, year, month = None, day = None):
        """
        Find Weekday using Zeller's Algorithm
        :param year:
        :param month:
        :param day:

        :return:
        """

        if month is None:
            month = 1

        if day is None:
            day = 1

        if month <= 2:
            month += 12
            year -= 1

        y = year % 100
        c = year // 100
        w = int(day + int((13 * (month + 1)) / 5) + y + int(y / 4) + int(c / 4) + 5 * c) % 7

        return (5, 6, 0, 1, 2, 3, 4)[w]

    @classmethod
    def days_in_month(cls, year, month):
        """

        :param year:
        :param month:
        :return:
        """
        days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if (year % 400 == 0) or ((year % 4 == 0) and (year % 100 != 0)):
            days[1] += 1
        return days[month - 1]

    @classmethod
    def weeks_in_month(cls, year, month):
        """

        :param year:
        :param month:
        :return:
        """
        first_sunday = 7 - cls.weekday(year, month, 1)

        weeks = list()
        weeks.append((1, first_sunday))
        _days_in_month = cls.days_in_month(year, month)
        for i in range(0, 5):
            if _days_in_month < first_sunday + (i+1) * 7:
                weeks.append((weeks[i][1] + 1, _days_in_month))
                break
            else:
                weeks.append((weeks[i][1] + 1, first_sunday + (i+1) * 7))

        return weeks

    @classmethod
    def day_from_week_and_weekday(cls, year, month, week, wd):
        weeks = cls.weeks_in_month(year, month)
        month_days = cls.days_in_month(year, month)

        day = weeks[week - 1][0] + wd

        if day <= month_days:
            return day

        # Return the day from last week of the month that contains the weekday
        for i in range(1, 3):
            day = weeks[-i][0] + wd
            if day <= month_days:
                return day

        raise Exception('Non existent day')

    @classmethod
    def _log(cls, message: str):
        if callable(cls._logger):
            cls._logger(message)

    @staticmethod
    def _validate_hostname(hostname: str):
        # strip exactly one dot from the right, if present
        if hostname[-1] == ".":
            hostname = hostname[:-1]

        if not (0 < len(hostname) <= 253):
            return False

        labels = hostname.split('.')

        # the TLD must be not all-numeric
        if re.match(r'[0-9]+$', labels[-1]):
            return False

        return True

    @classmethod
    def _select_epoch(cls, epoch, epoch_list):
        if not isinstance(epoch_list, tuple):
            raise ValueError('Invalid parameter: epoch_list must be a tuple')

        if isinstance(epoch, int) and epoch in (0, 1, 2):
            return epoch_list[epoch]
        elif epoch is None:
            return 0
        else:
            raise ValueError('Invalid parameter: epoch')