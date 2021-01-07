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
    DST_WEEK_FIFTH = 5
    DST_WEEK_SIXTH = 6

    DST_DOW_MON = 0
    DST_DOW_TUE = 1
    DST_DOW_WED = 2
    DST_DOW_THU = 3
    DST_DOW_FRI = 4
    DST_DOW_SAT = 5
    DST_DOW_SUN = 6

    _NTP_DELTA_1900_1970 = 2208988800  # Seconds between 1900 and 1970
    _NTP_DELTA_1900_2000 = 3155673600  # Seconds between 1900 and 2000
    _NTP_DELTA_1970_2000 = 946684800   # Seconds between 1970 and 2000 = _NTP_DELTA_1900_2000 - _NTP_DELTA_1900_1970

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

    @classmethod
    def set_datetime_callback(cls, callback):
        """
        Set a callback function for reading and writing a RTC chip. Separation of the low level functions for accessing
        the RTC allows the library te be chip-agnostic. With this strategy you can manipulate the internal, any
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
        """
        Set a callback function for the logger, it's parameter is a callback function - func(message: str)
        The default logger is print() and to set it just call the setter without any parameters.
        To disable logging, set the callback to "None"

        :param callback: A callable object. Default value = print; None = disabled logger; Any other value raises exception
        """

        if callback is not None and not callable(callback):
            raise ValueError('Invalid parameter: callback={} must be a callable object or None to disable logging'.format(callback))

        cls._log_callback = callback

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
    def set_dst_start(cls, month: int, week: int, weekday: int, hour: int):
        """

        :param month:
        :param week:
        :param weekday:
        :param hour:
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
        """

        :return:
        """

        return cls._dst_start

    @classmethod
    def set_dst_end(cls, month: int, week: int, weekday: int, hour: int):
        """

        :param month:
        :param week:
        :param weekday:
        :param hour:
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
        """

        :return:
        """

        return cls._dst_end

    @classmethod
    def set_dst_time_bias(cls, bias: int):
        """
        Set Daylight Saving Time bias expressed in minutes

        :param bias: minutes of the DST bias. Correct values are 30, 60, 90 and 120
        """

        if not isinstance(bias, int) or bias not in (30, 60, 90, 120):
            raise ValueError("Invalid parameter: bias={} represents minutes offset and must be either 30, 60, 90 or 120".format(bias))

        # Convert the time bias to seconds
        cls._dst_bias = bias * 60

    @classmethod
    def get_dst_time_bias(cls):
        """

        :return:
        """

        # Convert the time bias to minutes
        return cls._dst_bias // 60

    @classmethod
    def dst(cls):
        """
        Calculate if DST is currently in effect and return the bias in seconds.

        :return: Calculated DST bias
        """

        # When DST is disabled, return 0
        if not cls._dst_start or not cls._dst_end:
            return 0

        date = cls._datetime()
        year = date[0]
        month = date[1]
        day = date[2]

        if cls._dst_start[0] < month < cls._dst_end[0]:
            return cls._dst_bias
        elif cls._dst_start[0] == month:
            # Switch time in hours since the beginning of the month
            switch_hour = cls.day_from_week_and_weekday(year, month, cls._dst_start[1], cls._dst_start[2]) * 24 + cls._dst_start[3]
            if (day * 24 + date[4]) >= switch_hour:
                return cls._dst_bias
        elif cls._dst_end[0] == month:
            # Switch time in hours since the beginning of the month
            switch_hour = cls.day_from_week_and_weekday(year, month, cls._dst_end[1], cls._dst_end[2]) * 24 + cls._dst_end[3]
            if (day * 24 + date[4]) < switch_hour:
                return cls._dst_bias

        return 0

    @classmethod
    def set_ntp_timeout(cls, timeout_s: int = 1):
        """
        Set a timeout of the requests to the NTP servers. Default is 1 sec

        :param timeout_s: Timeout in seconds of the request
        """

        if not isinstance(timeout_s, int):
            raise ValueError('Invalid parameter: timeout_s={} must be int'.format(timeout_s))

        cls._ntp_timeout_s = timeout_s

    @classmethod
    def ntp_timeout(cls):
        """
        Get the timeout of the requests to the NTP servers

        :return: Timeout in seconds
        """

        return cls._ntp_timeout_s

    @classmethod
    def hosts(cls):
        """
        Get the list of NTP servers as a tuple

        :return: Tuple with the NTP servers
        """

        return tuple(cls._hosts)

    @classmethod
    def set_hosts(cls, value: list):
        """
        Set a list with NTP servers

        :param value: A tuple containing NTP servers. Can contain hostnames or IP addresses
        """

        cls._hosts.clear()

        for host in value:
            if cls._validate_hostname(host):
                cls._hosts.append(host)

    @classmethod
    def timezone(cls):
        """
        Get the timezone as a tuple

        :return: A tuple with the timezone in the form (hour, minute)
        """

        return cls._timezone // 3600, (cls._timezone % 3600) // 60

    @classmethod
    def set_timezone(cls, hour: int, minute: int = 0):
        """
        Set the timezone. The typical time shift is multiple of whole hours, but a time shift with minutes is also
        possible. A validity chek is made for the correctness of the timezone.

        :param hour: hours offset of the timezone. Type is 'int'
        :param minute: minutes offset of the timezone. Type is 'int'
        """

        if (
                (minute == 0 and not (-12 <= hour <= 12)) or
                (minute == 30 and hour not in (-9, -3, 3, 4, 5, 6, 9, 10)) or
                (minute == 45 and hour not in (5, 8, 12))
        ):
            raise Exception('Timezone is invalid')

        cls._timezone = hour * 3600 + minute * 60

    @classmethod
    def time(cls):
        us = cls.time_us()
        lt = time.localtime(us // 1000000)
        return lt[0], lt[1], lt[2], lt[6], lt[7], lt[3], lt[4], lt[5], us % 1000000

    @classmethod
    def time_s(cls, epoch = None):
        """
        Return the current time in seconds according to the selected 'epoch'

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :return: the time in seconds since the selected epoch
        """

        return cls.time_us(epoch) // 1000000

    @classmethod
    def time_ms(cls, epoch = None):
        """
        Return the current time in milliseconds according to the selected epoch

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :return: the time in milliseconds since the selected epoch
        """

        return cls.time_us(epoch) // 1000

    @classmethod
    def time_us(cls, epoch = None):
        """
        Return the current time in microseconds according to the selected epoch

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :return: the time in microseconds since the selected epoch
        """

        epoch = cls._select_epoch(epoch, (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0))

        # Do not take the value when on the verge of the next second
        # This is required to ensure that the sec and usec will be read within the boundaries of one second
        us = cls._datetime()[7]
        if us >= 995000:
            time.sleep_us(100000 - us)

        return (time.time() + epoch + cls._timezone + cls.dst()) * 1000000 + cls._datetime()[7]

    @classmethod
    def network_time(cls, epoch = None):
        """
        Get the accurate time from the first valid NTP server in the list with microsecond precision. When the server
        does not respond within the timeout period, the next server in the list is used. The default timeout is 1 sec.
        When none of the servers respond, throw an Exception.

        :param epoch: an epoch according to which the time will be be calculated.
        Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
        :return: a tuple with the NTP time and a timestamp. First position contains the accurate time from the NTP
        server in nanoseconds. The second position in the tuple is a timestamp in microseconds taken at the time the
        request to the server was sent. This timestamp can be used later to compensate for the difference in time from
        when the request was sent and the current timestamp, taken with time.ticks_us()
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
        cls._datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], ntp_us % 1000000))
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

        rtc_us = cls.time_us(cls.EPOCH_2000)
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

        delta_time_rtc = cls.time_us(cls.EPOCH_2000) - max(cls._rtc_last_sync, cls._drift_last_compensate)
        delta_time_real = (1000000 * delta_time_rtc) // (1000000 + ppm_drift)

        return delta_time_rtc - delta_time_real

    @classmethod
    def drift_compensate(cls, compensate_us: int):
        """

        :param compensate_us:
        """

        if not isinstance(compensate_us, int):
            raise ValueError('Invalid parameter: compensate_us={} must be int'.format(compensate_us))

        rtc_us = cls.time_us(cls.EPOCH_2000)
        rtc_us += compensate_us
        lt = time.localtime(rtc_us // 1000000)
        cls._datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], rtc_us % 1000000))
        cls._drift_last_compensate = rtc_us

    @classmethod
    def weekday(cls, year, month, day):
        """
        Find Weekday using Zeller's Algorithm, from the year, month and day

        :param year:
        :param month:
        :param day:
        :return:
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

        return (5, 6, 0, 1, 2, 3, 4)[w]

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

        if not isinstance(year, int) or not 1 <= year:
            raise ValueError('Invalid parameter: year={} must be int and greater than 0'.format(year))

        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError('Invalid parameter: month={} must be int and between 1 and 12'.format(month))

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
        days = cls.days_in_month(year, month)
        day = weeks[week - 1][0] + weekday

        if day <= days:
            return day

        # Return the day from last week of the month that contains the weekday
        for i in range(1, 3):
            day = weeks[-i][0] + weekday
            if day <= days:
                return day

        raise Exception('Non existent day')

    @classmethod
    def _log(cls, message: str):
        if callable(cls._log_callback):
            cls._log_callback(message)

    @classmethod
    def _datetime(cls, dt = None):
        if not callable(cls._datetime_callback):
            Exception('No callback set to access the RTC')

        if isinstance(dt, tuple) and len(dt) == 8:
            cls._datetime_callback(dt)
        elif dt is None:
            return cls._datetime_callback()
        else:
            raise ValueError('Invalid parameter: dt={} must be a 8-tuple(year, month, day, weekday, hours, minutes, seconds, subseconds)'.format(hostname))

    @staticmethod
    def _validate_hostname(hostname: str):
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
        if epoch is None or epoch_list is None:
            return 0

        if not isinstance(epoch, int) or not 0 <= epoch <= 2:
            raise ValueError('Invalid parameter: epoch={}'.format(epoch))

        if not isinstance(epoch_list, tuple) or len(epoch_list) != 3:
            raise ValueError('Invalid parameter: epoch_list={} must be a tuple and its length must be 3'.format(epoch_list))

        return epoch_list[epoch]
