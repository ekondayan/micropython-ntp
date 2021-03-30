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

from micropython import const

_NTP_DELTA_1900_1970 = const(2208988800)  # Seconds between 1900 and 1970
_NTP_DELTA_1900_2000 = const(3155673600)  # Seconds between 1900 and 2000
_NTP_DELTA_1970_2000 = const(946684800)  # Seconds between 1970 and 2000 = _NTP_DELTA_1900_2000 - _NTP_DELTA_1900_1970

class Ntp:
    EPOCH_1900 = const(0)
    EPOCH_1970 = const(1)
    EPOCH_2000 = const(2)

    DST_MONTH_JAN = const(1)
    DST_MONTH_FEB = const(2)
    DST_MONTH_MAR = const(3)
    DST_MONTH_APR = const(4)
    DST_MONTH_MAY = const(5)
    DST_MONTH_JUN = const(6)
    DST_MONTH_JUL = const(7)
    DST_MONTH_AUG = const(8)
    DST_MONTH_SEP = const(9)
    DST_MONTH_OCT = const(10)
    DST_MONTH_NOV = const(11)
    DST_MONTH_DEC = const(12)

    DST_WEEK_FIRST = const(1)
    DST_WEEK_SECOND = const(2)
    DST_WEEK_THIRD = const(3)
    DST_WEEK_FORTH = const(4)
    DST_WEEK_FIFTH = const(5)
    DST_WEEK_LAST = const(6)

    DST_DOW_MON = const(0)
    DST_DOW_TUE = const(1)
    DST_DOW_WED = const(2)
    DST_DOW_THU = const(3)
    DST_DOW_FRI = const(4)
    DST_DOW_SAT = const(5)
    DST_DOW_SUN = const(6)

    _log_callback = print
    _datetime_callback = None
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

    # ========================================
    # Preallocate ram to prevent fragmentation
    # ========================================
    __weekdays = (5, 6, 0, 1, 2, 3, 4)
    __days = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    __ntp_msg = bytearray(48)
    # ========================================

    @classmethod
    def set_datetime_callback(cls, callback):
        """ Set a callback function for reading and writing a RTC chip. Separation of the low level functions for accessing
        the RTC allows the library te be chip-agnostic. With this strategy you can manipulate the internal RTC, any
        external or even multiple RTC chips if you wish.

        :param callback: A callable object. With no arguments, this callable returns an 8-tuple with the
        current date and time. With 1 argument (being an 8-tuple) it sets the date and time of the RTC. The format
        of the 8-tuple is (year, month, day, weekday, hours, minutes, seconds, subseconds)
        """

        if not callable(callback):
            ValueError('Invalid parameter: callback={} must be a callable object'.format(callback))

        cls._datetime_callback = callback

    @classmethod
    def set_logger_callback(cls, callback = print):
        """ Set a callback function for the logger, it's parameter is a callback function - func(message: str)
        The default logger is print() and to set it just call the setter without any parameters.
        To disable logging, set the callback to "None"

        :param callback: A callable object. Default value = print; None = disabled logger; Any other value raises exception
        """

        if callback is not None and not callable(callback):
            raise ValueError('Invalid parameter: callback={} must be a callable object or None to disable logging'.format(callback))

        cls._log_callback = callback

    @classmethod
    def set_dst(cls, start: tuple, end: tuple, bias: int):
        """ Set DST in one pass

        :param start: 4-tuple(month, week, weekday, hour) start of DST
        :param end:4-tuple(month, week, weekday, hour) end of DST
        :param bias: integer Daylight Saving Time bias expressed in minutes
        """
        if not isinstance(start, tuple) or not len(start) == 4:
            raise ValueError("Invalid parameter: start={} must be a 4-tuple(month, week, weekday, hour)".format(start))
        elif not isinstance(end, tuple) or not len(end) == 4:
            raise ValueError("Invalid parameter: end={} must be a 4-tuple(month, week, weekday, hour)".format(end))

        cls.set_dst_start(start[0], start[1], start[2], start[3])
        cls.set_dst_end(end[0], end[1], end[2], end[3])
        cls.set_dst_time_bias(bias)

    @classmethod
    def set_dst_start(cls, month: int, week: int, weekday: int, hour: int):
        """ Set the start point of DST

        :param month: integer in range 1(Jan) - 12(Dec)
        :param week: integer in range 1 - 6. Sometimes there are months where they can span over a 6 weeks ex. 05.2021
        :param weekday: integer in range 0(Mon) - 6(Sun)
        :param hour: integer in range 0 - 23
        """

        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError("Invalid parameter: month={} must be a integer between 1 and 12".format(month))
        elif not isinstance(week, int) or not 1 <= week <= 6:
            raise ValueError("Invalid parameter: week={} must be a integer between 1 and 6".format(week))
        elif not isinstance(weekday, int) or not 0 <= weekday <= 6:
            raise ValueError("Invalid parameter: weekday={} must be a integer between 0 and 6".format(weekday))
        elif not isinstance(hour, int) or not 0 <= hour <= 23:
            raise ValueError("Invalid parameter: hour={} must be a integer between 0 and 23".format(hour))

        cls._dst_start = (month, week, weekday, hour)

    @classmethod
    def get_dst_start(cls):
        """ Get the start point of DST

        :return: 4-tuple(month, week, weekday, hour)
        """

        return cls._dst_start

    @classmethod
    def set_dst_end(cls, month: int, week: int, weekday: int, hour: int):
        """ Set the end point of DST

        :param month: integer in range 1(Jan) - 12(Dec)
        :param week: integer in range 1 - 6. Sometimes there are months where they can span over a 6 weeks
        :param weekday: integer in range 0(Mon) - 6(Sun)
        :param hour: integer in range 0 - 23
        """

        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError("Invalid parameter: month={} must be a integer between 1 and 12".format(month))
        elif not isinstance(week, int) or not 1 <= week <= 6:
            raise ValueError("Invalid parameter: week={} must be a integer between 1 and 6".format(week))
        elif not isinstance(weekday, int) or not 0 <= weekday <= 6:
            raise ValueError("Invalid parameter: weekday={} must be a integer between 0 and 6".format(weekday))
        elif not isinstance(hour, int) or not 0 <= hour <= 23:
            raise ValueError("Invalid parameter: hour={} must be a integer between 0 and 23".format(hour))

        cls._dst_end = (month, week, weekday, hour)

    @classmethod
    def get_dst_end(cls):
        """ Get the end point of DST

        :return: 4-tuple(month, week, weekday, hour)
        """

        return cls._dst_end

    @classmethod
    def set_dst_time_bias(cls, bias: int):
        """ Set Daylight Saving Time bias expressed in minutes

        :param bias: minutes of the DST bias. Correct values are 30, 60, 90 and 120
        """

        if not isinstance(bias, int) or bias not in (30, 60, 90, 120):
            raise ValueError("Invalid parameter: bias={} represents minutes offset and must be either 30, 60, 90 or 120".format(bias))

        # Convert the time bias to seconds
        cls._dst_bias = bias * 60

    @classmethod
    def get_dst_time_bias(cls):
        """ Get Daylight Saving Time bias expressed in minutes

        :return: minutes of the DST bias. Valid values are 30, 60, 90 and 120
        """

        # Convert the time bias to minutes
        return cls._dst_bias // 60

    @classmethod
    def dst(cls):
        """ Calculate if DST is currently in effect and return the bias in seconds.

        :return: Calculated DST bias in seconds
        """

        # When DST is disabled, return 0
        if not cls._dst_start or not cls._dst_end:
            return 0

        dt = cls._datetime()
        # dt = (year, month, day, weekday, hours, minutes, seconds, subseconds)
        # index  0      1     2      3       4       5       6          7

        if cls._dst_start[0] < dt[1] < cls._dst_end[0]:
            return cls._dst_bias
        elif cls._dst_start[0] == dt[1]:
            # Switch time in hours since the beginning of the month
            switch_hour = cls.day_from_week_and_weekday(dt[0], dt[1], cls._dst_start[1], cls._dst_start[2]) * 24 + cls._dst_start[3]
            if (dt[2] * 24 + dt[4]) >= switch_hour:
                return cls._dst_bias
        elif cls._dst_end[0] == dt[1]:
            # Switch time in hours since the beginning of the month
            switch_hour = cls.day_from_week_and_weekday(dt[0], dt[1], cls._dst_end[1], cls._dst_end[2]) * 24 + cls._dst_end[3]
            if (dt[2] * 24 + dt[4]) < switch_hour:
                return cls._dst_bias

        return 0

    @classmethod
    def set_ntp_timeout(cls, timeout_s: int = 1):
        """ Set a timeout of the requests to the NTP servers. Default is 1 sec


        :param timeout_s: Timeout in seconds of the request
        """

        if not isinstance(timeout_s, int):
            raise ValueError('Invalid parameter: timeout_s={} must be int'.format(timeout_s))

        cls._ntp_timeout_s = timeout_s

    @classmethod
    def ntp_timeout(cls):
        """ Get the timeout of the requests to the NTP servers

        :return: Timeout in seconds
        """

        return cls._ntp_timeout_s

    @classmethod
    def hosts(cls):
        """ Get a tuple of NTP servers

        :return: Tuple with the NTP servers
        """

        return tuple(cls._hosts)

    @classmethod
    def set_hosts(cls, value: tuple):
        """ Set a tuple with NTP servers

        :param value: A tuple containing NTP servers. Can contain hostnames or IP addresses
        """

        cls._hosts.clear()

        for host in value:
            if cls._validate_hostname(host):
                cls._hosts.append(host)

    @classmethod
    def timezone(cls):
        """ Get the timezone as a tuple

        :return: The timezone as a 2-tuple(hour, minute)
        """

        return cls._timezone // 3600, (cls._timezone % 3600) // 60

    @classmethod
    def set_timezone(cls, hour: int, minute: int = 0):
        """ Set the timezone. The typical time shift is multiple of a whole hour, but a time shift with minutes is also
        possible. A basic validity chek is made for the correctness of the timezone.

        :param hour: hours offset of the timezone. Type is 'int'
        :param minute: minutes offset of the timezone. Type is 'int'
        """

        if not isinstance(hour, int):
            raise ValueError('Invalid parameter: hour={} must be int'.format(hour))

        if not isinstance(minute, int):
            raise ValueError('Invalid parameter: minute={} must be int'.format(minute))

        if (
                (minute == 0 and not (-12 <= hour <= 12)) or
                (minute == 30 and hour not in (-9, -3, 3, 4, 5, 6, 9, 10)) or
                (minute == 45 and hour not in (5, 8, 12))
        ):
            raise Exception('Invalid timezone for hour={} and minute={}'.format(hour, minute))

        cls._timezone = hour * 3600 + minute * 60

    @classmethod
    def time(cls, gmt: bool = False):
        """ Get a tuple with the date and time in GMT or local timezone + DST

        :param gmt: boolean according to GMT time
        :return: 9-tuple(year, month, day, weekday, yearday, hour, minute, second, us)
        """

        us = cls.time_us(gmt = gmt)
        lt = time.localtime(us // 1000_000)
        # lt = (year, month, day, hour, minute, second, weekday, yearday)
        # index  0      1     2    3      4       5       6         7

        return lt[0], lt[1], lt[2], lt[6], lt[7], lt[3], lt[4], lt[5], us % 1000_000

    @classmethod
    def time_s(cls, epoch = None, gmt: bool = False):
        """ Return the current time in seconds according to the selected epoch

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :param gmt: boolean according to GMT time
        :return: the time in seconds since the selected epoch
        """

        return cls.time_us(epoch = epoch, gmt = gmt) // 1000_000

    @classmethod
    def time_ms(cls, epoch = None, gmt: bool = False):
        """ Return the current time in milliseconds according to the selected epoch

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :param gmt: boolean according to GMT time
        :return: the time in milliseconds since the selected epoch
        """

        return cls.time_us(epoch = epoch, gmt = gmt) // 1000

    @classmethod
    def time_us(cls, epoch = None, gmt: bool = False):
        """ Return the current time in microseconds according to the selected epoch

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :param gmt: boolean according to GMT time
        :return: integer the time in microseconds since the selected epoch
        """

        epoch = cls._select_epoch(epoch, (_NTP_DELTA_1900_2000, _NTP_DELTA_1970_2000, 0))

        # Do not take the value when on the verge of the next second
        # This is required to ensure that the sec and usec will be read within the boundaries of one second
        us = cls._datetime()[7]
        if us >= 995000:
            time.sleep_us(100_000 - us)

        timezone_and_dst = 0 if gmt else (cls._timezone + cls.dst())
        return (time.time() + epoch + timezone_and_dst) * 1000_000 + cls._datetime()[7]

    @classmethod
    def network_time(cls, epoch = None):
        """ Get the accurate time from the first valid NTP server in the list with microsecond precision. When the server
        does not respond within the timeout period, the next server in the list is used. The default timeout is 1 sec.
        The timeout can be changed with `set_ntp_timeout()`. When none of the servers respond, throw an Exception.

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :return: 2-tuple(ntp time, timestamp). First position contains the accurate time(GMT) from the NTP
        server in nanoseconds. The second position in the tuple is a timestamp in microseconds taken at the time the
        request to the server was sent. This timestamp can be used later to compensate for the difference in time from
        when the request was sent and the current timestamp, taken with time.ticks_us()
        """

        if not any(cls._hosts):
            raise Exception('There are no valid Hostnames/IPs set for the time server')

        epoch = cls._select_epoch(epoch, (0, _NTP_DELTA_1900_1970, _NTP_DELTA_1900_2000))

        # Clear the NTP request packet
        cls.__ntp_msg[0] = 0x1B
        for i in range(1, len(cls.__ntp_msg)):
            cls.__ntp_msg[i] = 0

        for host in cls._hosts:
            s = None
            try:
                host_addr = socket.getaddrinfo(host, 123)[0][-1]
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(cls._ntp_timeout_s)
                s.sendto(cls.__ntp_msg, host_addr)
                timestamp = time.ticks_us()
                s.readinto(cls.__ntp_msg)
            except Exception as e:
                cls._log('(NTP) Network error: Host({}) Error({})'.format(host, str(e)))
                continue
            finally:
                if s is not None:
                    s.close()

            sec, nano = struct.unpack('!II', cls.__ntp_msg[40:48])
            if sec < epoch:
                cls._log('(NTP) Invalid packet: Host({})'.format(host))
                continue

            sec -= epoch
            micro = (nano * 1000_000) >> 32
            return sec * 1000_000 + micro, timestamp

        raise RuntimeError('Can not connect to any of the NTP servers')

    @classmethod
    def rtc_sync(cls):
        """ Synchronize the RTC with the time(GMT) from the NTP server. Timezone and DST are not added.

        """

        ntp_reading = cls.network_time(cls.EPOCH_2000)

        # Negate the execution time of all the instructions up to this point
        ntp_us = ntp_reading[0] + (time.ticks_us() - ntp_reading[1])
        lt = time.localtime(ntp_us // 1000_000)
        # lt = (year, month, day, hour, minute, second, weekday, yearday)
        # index  0      1     2    3      4       5       6         7

        cls._datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], ntp_us % 1000_000))
        cls._rtc_last_sync = ntp_us

    @classmethod
    def rtc_last_sync(cls, epoch: int = None, gmt: bool = False):
        """ Get the last time the RTC was synchronized.

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :param gmt: boolean according to GMT time
        :return: RTC last sync time in micro seconds by taking into account epoch and gmt
        """

        timezone_and_dst = 0 if gmt else (cls._timezone + cls.dst())
        epoch = cls._select_epoch(epoch, (_NTP_DELTA_1900_2000, _NTP_DELTA_1970_2000, 0))
        return 0 if cls._rtc_last_sync == 0 else cls._rtc_last_sync + (epoch + timezone_and_dst) * 1000_000

    @classmethod
    def drift_calculate(cls):
        """

        :return:
        """

        ntp_reading = cls.network_time(cls.EPOCH_2000)
        rtc_us = cls.time_us(epoch = cls.EPOCH_2000, gmt = True)
        # For maximum precision, negate the execution time of all the instructions up to this point
        ntp_us = ntp_reading[0] + (time.ticks_us() - ntp_reading[1])
        # Calculate the delta between thu current time and the last rtc sync or last compensate(whatever occurred last)
        rtc_sync_delta = ntp_us - max(cls._rtc_last_sync, cls._drift_last_compensate)
        rtc_ntp_delta = rtc_us - ntp_us
        cls._ppm_drift = (rtc_ntp_delta / rtc_sync_delta) * 1000_000
        cls._drift_last_calculate = ntp_us

        return cls._ppm_drift, rtc_ntp_delta

    @classmethod
    def drift_last_compensate(cls, epoch: int = None, gmt: bool = False):
        """ Get the last time the RTC was compensated based on the drift calculation.

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :param gmt: boolean according to GMT time
        :return: RTC last compensate time in micro seconds by taking into account epoch and gmt
        """

        timezone_and_dst = 0 if gmt else (cls._timezone + cls.dst())
        epoch = cls._select_epoch(epoch, (_NTP_DELTA_1900_2000, _NTP_DELTA_1970_2000, 0))
        return 0 if cls._drift_last_compensate == 0 else cls._drift_last_compensate + (epoch + timezone_and_dst) * 1000_000

    @classmethod
    def drift_last_calculate(cls, epoch: int = None, gmt: bool = False):
        """ Get the last time the drift was calculated

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :param gmt: boolean according to GMT time
        :return: the last drift calculation time in micro seconds by taking into account epoch and gmt
        """

        timezone_and_dst = 0 if gmt else (cls._timezone + cls.dst())
        epoch = cls._select_epoch(epoch, (_NTP_DELTA_1900_2000, _NTP_DELTA_1970_2000, 0))
        return 0 if cls._drift_last_calculate == 0 else cls._drift_last_calculate + (epoch + timezone_and_dst) * 1000_000

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
            raise ValueError('Invalid parameter: ppm={} must be float or int'.format(ppm))

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

        if not isinstance(ppm_drift, (float, int)):
            raise ValueError('Invalid parameter: ppm_drift={} must be float or int'.format(ppm_drift))

        delta_time_rtc = cls.time_us(epoch = cls.EPOCH_2000, gmt = True) - max(cls._rtc_last_sync, cls._drift_last_compensate)
        delta_time_real = (1000_000 * delta_time_rtc) // (1000_000 + ppm_drift)

        return delta_time_rtc - delta_time_real

    @classmethod
    def drift_compensate(cls, compensate_us: int):
        """

        :param compensate_us:
        """

        if not isinstance(compensate_us, int):
            raise ValueError('Invalid parameter: compensate_us={} must be int'.format(compensate_us))

        rtc_us = cls.time_us(epoch = cls.EPOCH_2000, gmt = True) + compensate_us
        lt = time.localtime(rtc_us // 1000_000)
        # lt = (year, month, day, hour, minute, second, weekday, yearday)
        # index  0      1     2    3      4       5       6         7

        cls._datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], rtc_us % 1000_000))
        cls._drift_last_compensate = rtc_us

    @classmethod
    def weekday(cls, year, month, day):
        """ Find Weekday using Zeller's Algorithm, from the year, month and day

        :param year:
        :param month:
        :param day:
        :return: integer 0(Mon) 1(Tue) 2(Wed) 3(Thu) 4(Fri) 5(Sat) to 6(Sun)
        """

        if not isinstance(year, int) or not 1 <= year:
            raise ValueError('Invalid parameter: year={} must be int and greater than 0'.format(year))

        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError('Invalid parameter: month={} must be int and between 1 and 12'.format(month))

        if not isinstance(day, int):
            raise ValueError('Invalid parameter: day={} must be int'.format(day))
        else:
            days = cls.days_in_month(year, month)
            if day > days:
                raise ValueError('Invalid parameter: day={} must be between 1 and {}'.format(day, days))

        if month <= 2:
            month += 12
            year -= 1

        y = year % 100
        c = year // 100
        w = int(day + int((13 * (month + 1)) / 5) + y + int(y / 4) + int(c / 4) + 5 * c) % 7

        return cls.__weekdays[w]

    @classmethod
    def days_in_month(cls, year, month):
        """

        :param year:
        :param month:
        :return:
        """

        if not isinstance(year, int) or not 1 <= year:
            raise ValueError('Invalid parameter: year={} must be int and greater than 0'.format(year))

        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError('Invalid parameter: month={} must be int and between 1 and 12'.format(month))

        if month == 2:
            if (year % 400 == 0) or ((year % 4 == 0) and (year % 100 != 0)):
                return cls.__days[1] + 1

        return cls.__days[month - 1]

    @classmethod
    def weeks_in_month(cls, year, month):
        """

        :param year: integer
        :param month:
        :return: integer The number of weeks in month
        """

        if not isinstance(year, int) or not 1 <= year:
            raise ValueError('Invalid parameter: year={} must be int and greater than 0'.format(year))

        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError('Invalid parameter: month={} must be int and between 1 and 12'.format(month))

        first_sunday = 7 - cls.weekday(year, month, 1)
        weeks_list = list()
        weeks_list.append((1, first_sunday))
        days_in_month = cls.days_in_month(year, month)
        for i in range(0, 5):
            if days_in_month <= first_sunday + (i + 1) * 7:
                weeks_list.append((weeks_list[i][1] + 1, days_in_month))
                break
            else:
                weeks_list.append((weeks_list[i][1] + 1, first_sunday + (i + 1) * 7))

        return weeks_list

    @classmethod
    def day_from_week_and_weekday(cls, year, month, week, weekday):
        """

        :param year:
        :param month:
        :param week:
        :param weekday:
        :return:
        """

        if not isinstance(year, int) or not 1 <= year:
            raise ValueError('Invalid parameter: year={} must be int and greater than 0'.format(year))

        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError('Invalid parameter: month={} must be int and between 1 and 12'.format(month))

        if not isinstance(week, int) or not 1 <= week <= 6:
            raise ValueError('Invalid parameter: week={} must be int in range 1-6'.format(week))

        if not isinstance(weekday, int) or not 0 <= weekday <= 6:
            raise ValueError('Invalid parameter: weekday={} must be int in range 0-6'.format(weekday))

        weeks = cls.weeks_in_month(year, month)
        days_in_month = cls.days_in_month(year, month)

        day = weeks[-1][0] if week > len(weeks) else weeks[week - 1][0]
        day += weekday

        if day <= days_in_month:
            return day

        return weeks[-2][0] + weekday

    @classmethod
    def _log(cls, message: str):
        """

        :param message:
        :return:
        """

        if callable(cls._log_callback):
            cls._log_callback(message)

    @classmethod
    def _datetime(cls, dt = None):
        """

        :param dt:
        :return:
        """

        if not callable(cls._datetime_callback):
            raise Exception('No callback set to access the RTC')

        if isinstance(dt, tuple) and len(dt) == 8:
            cls._datetime_callback(dt)
        elif dt is None:
            return cls._datetime_callback()
        else:
            raise ValueError(
                'Invalid parameter: dt={} must be a 8-tuple(year, month, day, weekday, hours, minutes, seconds, subseconds)'.format(dt))

    @staticmethod
    def _validate_hostname(hostname: str):
        """

        :param hostname:
        :return:
        """

        if not isinstance(hostname, str):
            raise ValueError('Invalid parameter: hostname={} must be a string'.format(hostname))

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
        """

        :param epoch:
        :param epoch_list:
        :return:
        """

        if epoch is None or epoch_list is None:
            return 0

        if not isinstance(epoch, int) or not 0 <= epoch <= 2:
            raise ValueError('Invalid parameter: epoch={}'.format(epoch))

        if not isinstance(epoch_list, tuple) or len(epoch_list) != 3:
            raise ValueError('Invalid parameter: epoch_list={} must be a tuple and its length must be 3'.format(epoch_list))

        return epoch_list[epoch]
