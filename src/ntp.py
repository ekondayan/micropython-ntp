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

try:
    from micropython import const
except ImportError:
    def const(v):
        return v

_NTP_DELTA_1900_1970 = const(2208988800)  # Seconds between 1900 and 1970
_NTP_DELTA_1900_2000 = const(3155673600)  # Seconds between 1900 and 2000
_NTP_DELTA_1970_2000 = const(946684800)  # Seconds between 1970 and 2000 = _NTP_DELTA_1900_2000 - _NTP_DELTA_1900_1970


class Ntp:
    EPOCH_1900 = const(0)
    EPOCH_1970 = const(1)
    EPOCH_2000 = const(2)

    MONTH_JAN = const(1)
    MONTH_FEB = const(2)
    MONTH_MAR = const(3)
    MONTH_APR = const(4)
    MONTH_MAY = const(5)
    MONTH_JUN = const(6)
    MONTH_JUL = const(7)
    MONTH_AUG = const(8)
    MONTH_SEP = const(9)
    MONTH_OCT = const(10)
    MONTH_NOV = const(11)
    MONTH_DEC = const(12)

    WEEK_FIRST = const(1)
    WEEK_SECOND = const(2)
    WEEK_THIRD = const(3)
    WEEK_FORTH = const(4)
    WEEK_FIFTH = const(5)
    WEEK_LAST = const(6)

    WEEKDAY_MON = const(0)
    WEEKDAY_TUE = const(1)
    WEEKDAY_WED = const(2)
    WEEKDAY_THU = const(3)
    WEEKDAY_FRI = const(4)
    WEEKDAY_SAT = const(5)
    WEEKDAY_SUN = const(6)

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
    # Time bias in seconds
    _dst_bias: int = 0
    # Cache the switch hour calculation
    _dst_cache_switch_hours = None

    # ========================================
    # Preallocate ram to prevent fragmentation
    # ========================================
    __weekdays = (5, 6, 0, 1, 2, 3, 4)
    __days = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    __ntp_msg = bytearray(48)

    @classmethod
    def set_datetime_callback(cls, callback):
        """ Set a callback function for reading and writing a RTC chip. Separation of the low level functions for accessing
        the RTC allows the library te be chip-agnostic. With this strategy you can manipulate the internal RTC, any
        external or even multiple RTC chips if you wish.

        Args:
            callback (function): A callable object. With no arguments, this callable returns an 8-tuple with the
                current date and time. With 1 argument (being an 8-tuple) it sets the date and time of the RTC. The format
                of the 8-tuple is (year, month, day, weekday, hours, minutes, seconds, subseconds)

                !!! NOTE !!!
                Monday is index 0
        """

        if not callable(callback):
            ValueError('Invalid parameter: callback={} must be a callable object'.format(callback))

        cls._datetime_callback = callback

    @classmethod
    def set_logger_callback(cls, callback = print):
        """ Set a callback function for the logger, it's parameter is a callback function - func(message: str)
        The default logger is print() and to set it just call the setter without any parameters.
        To disable logging, set the callback to "None".

        Args:
            callback (function): A callable object. Default value = print; None = disabled logger; Any other value raises exception
        """

        if callback is not None and not callable(callback):
            raise ValueError('Invalid parameter: callback={} must be a callable object or None to disable logging'.format(callback))

        cls._log_callback = callback

    @classmethod
    def set_dst(cls, start: tuple, end: tuple, bias: int):
        """ Set DST data in one pass.

        Args:
            start (tuple): 4-tuple(month, week, weekday, hour) start of DST
            end (tuple) :4-tuple(month, week, weekday, hour) end of DST
            bias (int): Daylight Saving Time bias expressed in minutes
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

        Args:
            month (int): number in range 1(Jan) - 12(Dec)
            week (int): integer in range 1 - 6. Sometimes there are months where they can span over a 6 weeks ex. 05.2021
            weekday (int): integer in range 0(Mon) - 6(Sun)
            hour (int): integer in range 0 - 23
        """

        if not isinstance(month, int) or not cls.MONTH_JAN <= month <= cls.MONTH_DEC:
            raise ValueError("Invalid parameter: month={} must be a integer between 1 and 12".format(month))
        elif not isinstance(week, int) or not cls.WEEK_FIRST <= week <= cls.WEEK_LAST:
            raise ValueError("Invalid parameter: week={} must be a integer between 1 and 6".format(week))
        elif not isinstance(weekday, int) or not cls.WEEKDAY_MON <= weekday <= cls.WEEKDAY_SUN:
            raise ValueError("Invalid parameter: weekday={} must be a integer between 0 and 6".format(weekday))
        elif not isinstance(hour, int) or not 0 <= hour <= 23:
            raise ValueError("Invalid parameter: hour={} must be a integer between 0 and 23".format(hour))

        cls._dst_start = (month, week, weekday, hour)

    @classmethod
    def get_dst_start(cls):
        """ Get the start point of DST.

        Returns:
            tuple: 4-tuple(month, week, weekday, hour)
        """

        return cls._dst_start

    @classmethod
    def set_dst_end(cls, month: int, week: int, weekday: int, hour: int):
        """ Set the end point of DST.

        Args:
            month (int): number in range 1(Jan) - 12(Dec)
            week (int): number in range 1 - 6. Sometimes there are months where they can span over a 6 weeks.
            weekday (int): number in range 0(Mon) - 6(Sun)
            hour (int): number in range 0 - 23
        """

        if not isinstance(month, int) or not cls.MONTH_JAN <= month <= cls.MONTH_DEC:
            raise ValueError("Invalid parameter: month={} must be a integer between 1 and 12".format(month))
        elif not isinstance(week, int) or not cls.WEEK_FIRST <= week <= cls.WEEK_LAST:
            raise ValueError("Invalid parameter: week={} must be a integer between 1 and 6".format(week))
        elif not isinstance(weekday, int) or not cls.WEEKDAY_MON <= weekday <= cls.WEEKDAY_SUN:
            raise ValueError("Invalid parameter: weekday={} must be a integer between 0 and 6".format(weekday))
        elif not isinstance(hour, int) or not 0 <= hour <= 23:
            raise ValueError("Invalid parameter: hour={} must be a integer between 0 and 23".format(hour))

        cls._dst_end = (month, week, weekday, hour)

    @classmethod
    def get_dst_end(cls):
        """ Get the end point of DST.

        Returns:
            tuple: 4-tuple(month, week, weekday, hour)
        """

        return cls._dst_end

    @classmethod
    def set_dst_time_bias(cls, bias: int):
        """ Set Daylight Saving Time bias expressed in minutes.

        Args:
            bias (int): minutes of the DST bias. Correct values are 30, 60, 90 and 120
        """

        if not isinstance(bias, int) or bias not in (30, 60, 90, 120):
            raise ValueError("Invalid parameter: bias={} represents minutes offset and must be either 30, 60, 90 or 120".format(bias))

        # Convert the time bias to seconds
        cls._dst_bias = bias * 60

    @classmethod
    def get_dst_time_bias(cls):
        """ Get Daylight Saving Time bias expressed in minutes.

        Returns:
            int: minutes of the DST bias. Valid values are 30, 60, 90 and 120
        """

        # Convert the time bias to minutes
        return cls._dst_bias // 60

    @classmethod
    def dst(cls):
        """ Calculate if DST is currently in effect and return the bias in seconds.

        Returns:
            int: Calculated DST bias in seconds
        """

        # When DST is disabled, return 0
        if not cls._dst_start or not cls._dst_end:
            return 0

        # dt = (year, month, day, hours, minutes, seconds, weekday, subseconds)
        # index  0      1     2      3       4       5       6          7
        dt = cls._datetime()

        if cls._dst_start[0] < dt[1] < cls._dst_end[0]:
            cls._dst_cache_switch_hours = None
            return cls._dst_bias
        elif dt[1] < cls._dst_start[0] or cls._dst_end[0] < dt[1]:
            cls._dst_cache_switch_hours = None
            return 0
        elif dt[1] == cls._dst_start[0]:
            # Cache the calculation for the switch time
            if cls._dst_cache_switch_hours is None:
                # Switch time in hours since the beginning of the month
                cls._dst_cache_switch_hours = cls.day_from_week_and_weekday(dt[0], dt[1], cls._dst_start[1], cls._dst_start[2]) * 24 + cls._dst_start[3]

            if (dt[2] * 24 + dt[3]) >= cls._dst_cache_switch_hours:
                return cls._dst_bias

        elif dt[1] == cls._dst_end[0]:
            # Cache the calculation for the switch time
            if cls._dst_cache_switch_hours is None:
                # Switch time in hours since the beginning of the month
                cls._dst_cache_switch_hours = cls.day_from_week_and_weekday(dt[0], dt[1], cls._dst_end[1], cls._dst_end[2]) * 24 + cls._dst_end[3]

            if (dt[2] * 24 + dt[3]) < cls._dst_cache_switch_hours:
                return cls._dst_bias

        return 0

    @classmethod
    def set_ntp_timeout(cls, timeout_s: int = 1):
        """ Set a timeout of the requests to the NTP servers. Default is 1 sec.

        Args:
            timeout_s (int): Timeout in seconds of the request
        """

        if not isinstance(timeout_s, int):
            raise ValueError('Invalid parameter: timeout_s={} must be int'.format(timeout_s))

        cls._ntp_timeout_s = timeout_s

    @classmethod
    def ntp_timeout(cls):
        """ Get the timeout for the requests to the NTP servers.

        Returns:
            int: Timeout in seconds
        """

        return cls._ntp_timeout_s

    @classmethod
    def hosts(cls):
        """ Get a tuple of NTP servers.

        Returns:
            tuple: NTP servers
        """

        return tuple(cls._hosts)

    @classmethod
    def set_hosts(cls, value: tuple):
        """ Set a tuple with NTP servers.

        Args:
            value (tuple): NTP servers. Can contain hostnames or IP addresses
        """

        cls._hosts.clear()

        for host in value:
            if cls._validate_host(host):
                cls._hosts.append(host)

    @classmethod
    def timezone(cls):
        """ Get the timezone as a tuple.

        Returns:
            tuple: The timezone as a 2-tuple(hour, minute)
        """

        return cls._timezone // 3600, (cls._timezone % 3600) // 60

    @classmethod
    def set_timezone(cls, hour: int, minute: int = 0):
        """ Set the timezone. The typical time shift is multiple of a whole hour, but a time shift with minutes is also
        possible. A basic validity chek is made for the correctness of the timezone.

        Args:
            hour (int): hours offset of the timezone. Type is 'int'
            minute (int): minutes offset of the timezone. Type is 'int'
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
    def time(cls, utc: bool = False):
        """ Get a tuple with the date and time in UTC or local timezone + DST.

        Args:
            utc (bool): the returned time will be according to UTC time

        Returns:
            tuple: 9-tuple(year, month, day, hour, minute, second, weekday, yearday, us)
        """

        us = cls.time_us(utc = utc)
        # (year, month, day, hour, minute, second, weekday, yearday) + (us,)
        return time.localtime(us // 1000_000) + (us % 1000_000, )

    @classmethod
    def time_s(cls, epoch = None, utc: bool = False):
        """ Return the current time in seconds according to the selected
        epoch, timezone and Daylight Saving Time. To skip the timezone and DST calculation
        set utc to True.

        Args:
            epoch (int): an epoch according to which the time will be calculated.
                Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
            utc (bool): the returned time will be according to UTC time

        Returns:
            int: the time in seconds since the selected epoch
        """

        return cls.time_us(epoch = epoch, utc = utc) // 1000_000

    @classmethod
    def time_ms(cls, epoch = None, utc: bool = False):
        """ Return the current time in milliseconds according to the selected
        epoch, timezone and Daylight Saving Time. To skip the timezone and DST calculation
        set utc to True.

        Args:
            epoch (int): an epoch according to which the time will be calculated.
                Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
            utc (bool): the returned time will be according to UTC time

        Returns:
            int: the time in milliseconds since the selected epoch
        """

        return cls.time_us(epoch = epoch, utc = utc) // 1000

    @classmethod
    def time_us(cls, epoch = None, utc: bool = False):
        """ Return the current time in microseconds according to the selected
        epoch, timezone and Daylight Saving Time. To skip the timezone and DST calculation
        set utc to True.

        Args:
            epoch (int): an epoch according to which the time will be calculated.
                Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
            utc (bool): the returned time will be according to UTC time

        Returns:
            int: integer the time in microseconds since the selected epoch
        """

        epoch = cls._select_epoch(epoch)

        # Do not take the value when on the verge of the next second
        # This is required to ensure that the sec and usec will be read within the boundaries of one second
        us = cls._datetime()[7]
        if us >= 995000:
            time.sleep_us(100_000 - us)

        timezone_and_dst = 0 if utc else (cls._timezone + cls.dst())
        dt = cls._datetime()
        return (time.mktime((dt[0], dt[1], dt[2], dt[3], dt[4], dt[5], 0, 0, 0)) + epoch + timezone_and_dst) * 1000_000 + dt[7]

    @classmethod
    def network_time(cls, epoch = None):
        """ Get the accurate time from the first valid NTP server in the list with microsecond precision. When the server
        does not respond within the timeout period, the next server in the list is used. The default timeout is 1 sec.
        The timeout can be changed with `set_ntp_timeout()`. When none of the servers respond, throw an Exception.

        Args:
            epoch (int): an epoch according to which the time will be calculated.
                Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000

        Returns:
            tuple: 2-tuple(ntp time, timestamp). First position contains the accurate time(UTC) from the NTP
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
    def rtc_sync(cls, new_time = None):
        """ Synchronize the RTC with the time from the NTP server. To bypass the NTP server,
        you can pass an optional parameter with the new time. This is useful when your device has
        an accurate RTC on board, which can be used instead of the costly NTP queries.

        Args:
            new_time (tuple, None): None or 2-tuple(time, timestamp). If None, the RTC will be synchronized
                from the NTP server. If 2-tuple is passed, the RTC will be synchronized with the given value.
                The 2-tuple format is (time, timestamp), where:

                * time = the micro second time in UTC since epoch 00:00:00 on 1 January 2000

                * timestamp = micro second timestamp at the moment the time was sampled
        """

        if new_time is None:
            new_time = cls.network_time(cls.EPOCH_2000)
        elif not isinstance(new_time, tuple) or not len(new_time) == 2:
            raise ValueError('Invalid parameter: new_time={} must be a either None or 2-tuple(time, timestamp)'.format(ppm))

        # Negate the execution time of all the instructions up to this point
        ntp_us = new_time[0] + (time.ticks_us() - new_time[1])
        lt = time.localtime(ntp_us // 1000_000)
        # lt = (year, month, day, hour, minute, second, weekday, yearday)
        # index  0      1     2    3      4       5       6         7

        cls._datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], ntp_us % 1000_000))
        cls._rtc_last_sync = ntp_us

    @classmethod
    def rtc_last_sync(cls, epoch: int = None, utc: bool = False):
        """ Get the last time the RTC was synchronized.

        Args:
            epoch (int): an epoch according to which the time will be calculated.
                Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
            utc (bool): the returned time will be according to UTC time

        Returns:
            int: RTC last sync time in micro seconds by taking into account epoch and utc
        """

        timezone_and_dst = 0 if utc else (cls._timezone + cls.dst())
        epoch = cls._select_epoch(epoch)
        return 0 if cls._rtc_last_sync == 0 else cls._rtc_last_sync + (epoch + timezone_and_dst) * 1000_000

    @classmethod
    def drift_calculate(cls, new_time = None):
        """ Calculate the drift of the RTC. Compare the time from the RTC with the time
        from the NTP server and calculates the drift in ppm units and the absolute drift
        time in micro seconds.  To bypass the NTP server, you can pass an optional parameter
        with the new time. This is useful when your device has an accurate RTC on board,
        which can be used instead of the costly NTP queries.
        To be able to calculate the drift, the RTC has to be
        synchronized first. More accurate results can be achieved if the time between last
        RTC synchronization and calling this function is increased. Practical tests shows
        that the minimum time from the last RTC synchronization has to be at least 20 min.
        To get more stable and reliable data, periods of more than 2 hours are suggested.
        The longer the better.
        Once the drift is calculated, the device can go offline and periodically call
        drift_compensate() to keep the RTC accurate. To calculate the drift in absolute
        micro seconds call drift_us(). Example: drift_compensate(drift_us()).
        The calculated drift is stored and can be retrieved later with drift_ppm().

        Args:
            new_time (tuple): None or 2-tuple(time, timestamp). If None, the RTC will be synchronized
                from the NTP server. If 2-tuple is passed, the RTC will be compensated with the given value.
                The 2-tuple format is (time, timestamp), where:

                * time = the micro second time in UTC since epoch 00:00:00 on 1 January 2000

                * timestamp = micro second timestamp in CPU ticks at the moment the time was sampled.
                              Example:
                                  from time import ticks_us
                                  timestamp = ticks_us()

        Returns:
            tuple: 2-tuple(ppm, us) ppm is a float and represents the calculated drift in ppm
                units; us is integer and contains the absolute drift in micro seconds.
                Both parameters can have negative and positive values. The sign shows in which
                direction the RTC is drifting. Positive values represent a RTC that is speeding,
                while negative values represent RTC that is lagging
        """

        # The RTC has not been synchronized, and the actual drift can not be calculated
        if cls._rtc_last_sync == 0 and cls._drift_last_compensate == 0:
            return 0.0, 0

        if new_time is None:
            new_time = cls.network_time(cls.EPOCH_2000)
        elif not isinstance(new_time, tuple) or not len(new_time) == 2:
            raise ValueError('Invalid parameter: new_time={} must be a either None or 2-tuple(time, timestamp)'.format(ppm))

        rtc_us = cls.time_us(epoch = cls.EPOCH_2000, utc = True)
        # For maximum precision, negate the execution time of all the instructions up to this point
        ntp_us = new_time[0] + (time.ticks_us() - new_time[1])
        # Calculate the delta between the current time and the last rtc sync or last compensate(whatever occurred last)
        rtc_sync_delta = ntp_us - max(cls._rtc_last_sync, cls._drift_last_compensate)
        rtc_ntp_delta = rtc_us - ntp_us
        cls._ppm_drift = (rtc_ntp_delta / rtc_sync_delta) * 1000_000
        cls._drift_last_calculate = ntp_us

        return cls._ppm_drift, rtc_ntp_delta

    @classmethod
    def drift_last_compensate(cls, epoch: int = None, utc: bool = False):
        """ Get the last time the RTC was compensated based on the drift calculation.

        Args:
            epoch (int): an epoch according to which the time will be calculated.
                Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
            utc (bool): the returned time will be according to UTC time

        Returns:
            int: RTC last compensate time in micro seconds by taking into account epoch and utc
        """

        timezone_and_dst = 0 if utc else (cls._timezone + cls.dst())
        epoch = cls._select_epoch(epoch)
        return 0 if cls._drift_last_compensate == 0 else cls._drift_last_compensate + (epoch + timezone_and_dst) * 1000_000

    @classmethod
    def drift_last_calculate(cls, epoch: int = None, utc: bool = False):
        """ Get the last time the drift was calculated.

        Args:
            epoch (int): an epoch according to which the time will be calculated.
                Possible values: Ntp.EPOCH_1900; Ntp.EPOCH_1970; Ntp.EPOCH_2000
            utc (bool): the returned time will be according to UTC time

        Returns:
            int: the last drift calculation time in micro seconds by taking into account epoch and utc
        """

        timezone_and_dst = 0 if utc else (cls._timezone + cls.dst())
        epoch = cls._select_epoch(epoch)
        return 0 if cls._drift_last_calculate == 0 else cls._drift_last_calculate + (epoch + timezone_and_dst) * 1000_000

    @classmethod
    def drift_ppm(cls):
        """ Get the calculated or manually set drift in ppm units.

        Returns:
            float: positive or negative number containing the drift value in ppm units
        """

        return cls._ppm_drift

    @classmethod
    def set_drift_ppm(cls, ppm: float):
        """ Manually set the drift in ppm units. If you know in advance the actual drift you can
        set it with this function.
        The ppm can be calculated in advance and stored in a Non-Volatile Storage as calibration
        data. That way the drift_calculate() as well as the initial long wait period can be skipped.

        Args:
            ppm (float, int): positive or negative number containing the drift value in ppm units.
                Positive values represent a speeding, while negative values represent a lagging RTC
        """

        if not isinstance(ppm, (float, int)):
            raise ValueError('Invalid parameter: ppm={} must be float or int'.format(ppm))

        cls._ppm_drift = float(ppm)

    @classmethod
    def drift_us(cls, ppm_drift: float = None):
        """ Calculate the drift in absolute micro seconds.

        Args:
            ppm_drift (float, None): if None, use the previously calculated or manually set ppm.
                If you pass a value other than None, the drift is calculated according to this
                value

        Returns:
            int: number containing the calculated drift in micro seconds.
                Positive values represent a speeding, while negative values represent a lagging RTC
        """

        if cls._rtc_last_sync == 0 and cls._drift_last_compensate == 0:
            return 0

        if ppm_drift is None:
            ppm_drift = cls._ppm_drift

        if not isinstance(ppm_drift, (float, int)):
            raise ValueError('Invalid parameter: ppm_drift={} must be float or int'.format(ppm_drift))

        delta_time_rtc = cls.time_us(epoch = cls.EPOCH_2000, utc = True) - max(cls._rtc_last_sync, cls._drift_last_compensate)
        delta_time_real = int((1000_000 * delta_time_rtc) // (1000_000 + ppm_drift))

        return delta_time_rtc - delta_time_real

    @classmethod
    def drift_compensate(cls, compensate_us: int):
        """ Compensate the RTC by adding the compensate_us parameter to it. The value can be
        positive or negative, depending on how you wish to compensate the RTC.

        Args:
            compensate_us (int): the microseconds that will be added to the RTC
        """

        if not isinstance(compensate_us, int):
            raise ValueError('Invalid parameter: compensate_us={} must be int'.format(compensate_us))

        rtc_us = cls.time_us(epoch = cls.EPOCH_2000, utc = True) + compensate_us
        lt = time.localtime(rtc_us // 1000_000)
        # lt = (year, month, day, hour, minute, second, weekday, yearday)
        # index  0      1     2    3      4       5       6         7

        cls._datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], rtc_us % 1000_000))
        cls._drift_last_compensate = rtc_us

    @classmethod
    def weekday(cls, year: int, month: int, day: int):
        """ Find Weekday using Zeller's Algorithm, from the year, month and day.

        Args:
            year (int): number greater than 1
            month (int): number in range 1(Jan) - 12(Dec)
            day (int): number in range 1-31

        Returns:
            int: 0(Mon) 1(Tue) 2(Wed) 3(Thu) 4(Fri) 5(Sat) to 6(Sun)
        """

        if not isinstance(year, int) or not 1 <= year:
            raise ValueError('Invalid parameter: year={} must be int and greater than 1'.format(year))
        elif not isinstance(month, int) or not cls.MONTH_JAN <= month <= cls.MONTH_DEC:
            raise ValueError('Invalid parameter: month={} must be int in range 1-12'.format(month))

        days = cls.days_in_month(year, month)
        if day > days:
            raise ValueError('Invalid parameter: day={} is greater than the days in month({})'.format(day, days))

        if month <= 2:
            month += 12
            year -= 1

        y = year % 100
        c = year // 100
        w = int(day + int((13 * (month + 1)) / 5) + y + int(y / 4) + int(c / 4) + 5 * c) % 7

        return cls.__weekdays[w]

    @classmethod
    def days_in_month(cls, year, month):
        """ Calculate how many days are in a given year and month

        Args:
            year (int): number greater than 1
            month (int): number in range 1(Jan) - 12(Dec)

        Returns:
            int: the number of days in the given month
        """

        if not isinstance(year, int) or not 1 <= year:
            raise ValueError('Invalid parameter: year={} must be int and greater than 1'.format(year))
        elif not isinstance(month, int) or not cls.MONTH_JAN <= month <= cls.MONTH_DEC:
            raise ValueError('Invalid parameter: month={} must be int in range 1-12'.format(month))

        if month == cls.MONTH_FEB:
            if (year % 400 == 0) or ((year % 4 == 0) and (year % 100 != 0)):
                return cls.__days[1] + 1

        return cls.__days[month - 1]

    @classmethod
    def weeks_in_month(cls, year, month):
        """ Split the month into tuples of weeks. The definition of a week is from Mon to Sun.
        If a month starts on a day different from Monday, the first week will be: day 1 to the day of the
        first Sunday. If a month ends on a day different from the Sunday, the last week will be: the last
        Monday till the end of the month. A month can have up to 6 weeks in it.
        For example if we run this function for May 2021, the result will be:
        [(1, 2), (3, 9), (10, 16), (17, 23), (24, 30), (31, 31)]. You can clearly see that
        the first week consists of just two days: Sat and Sun; the last week consists of just a single
        day: Mon

        Args:
            year (int): number greater than 1
            month (int): number in range 1(Jan) - 12(Dec)

        Returns:
            list: 2-tuples of weeks. Each tuple contains the first and the last day of the current week.
                Example result for May 2021: [(1, 2), (3, 9), (10, 16), (17, 23), (24, 30), (31, 31)]
        """

        if not isinstance(year, int) or not 1 <= year:
            raise ValueError('Invalid parameter: year={} must be int and greater than 1'.format(year))
        elif not isinstance(month, int) or not cls.MONTH_JAN <= month <= cls.MONTH_DEC:
            raise ValueError('Invalid parameter: month={} must be int in range 1-12'.format(month))

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
        """ Calculate the day based on year, month, week and weekday. If the selected week is
        outside the boundaries of the month, the last weekday of the month will be returned.
        Otherwise, if the weekday is within the boundaries of the month but is outside the
        boundaries of the week, raise an exception. This behaviour is desired when you want
        to select the last weekday of the month, like the last Sunday of October or the
        last Sunday of March.
        Example: day_from_week_and_weekday(2021, Ntp.MONTH_MAR, Ntp.WEEK_LAST, Ntp.WEEKDAY_SUN)
                 day_from_week_and_weekday(2021, Ntp.MONTH_OCT, Ntp.WEEK_LAST, Ntp.WEEKDAY_SUN)

        Args:
            year (int): number greater than 1
            month (int): number in range 1(Jan) - 12(Dec)
            week (int): number in range 1-6
            weekday (int): number in range 0(Mon)-6(Sun)

        Returns:
            int: the calculated day. If the day is outside the boundaries of the month, returns
                the last weekday in the month. If the weekday is outside the boundaries of the
                given week, raise an exception
        """

        if not isinstance(year, int) or not 1 <= year:
            raise ValueError('Invalid parameter: year={} must be int and greater than 1'.format(year))
        elif not isinstance(month, int) or not cls.MONTH_JAN <= month <= cls.MONTH_DEC:
            raise ValueError('Invalid parameter: month={} must be int in range 1-12'.format(month))
        elif not isinstance(week, int) or not cls.WEEK_FIRST <= week <= cls.WEEK_LAST:
            raise ValueError('Invalid parameter: week={} must be int in range 1-6'.format(week))
        elif not isinstance(weekday, int) or not cls.WEEKDAY_MON <= weekday <= cls.WEEKDAY_SUN:
            raise ValueError('Invalid parameter: weekday={} must be int in range 0-6'.format(weekday))

        weeks = cls.weeks_in_month(year, month)
        days_in_month = cls.days_in_month(year, month)

        week_tuple = weeks[-1] if week > len(weeks) else weeks[week - 1]
        day = week_tuple[0] + weekday

        # If the day is outside the boundaries of the month, select the week before the last
        # This behaviour guarantees to return the last weekday of the month
        if day > days_in_month:
            return weeks[-2][0] + weekday

        # The desired weekday overflow the last day of the week
        if day > week_tuple[1]:
            raise Exception('The weekday does not exists in the selected week')

        return day

    @classmethod
    def _log(cls, message: str):
        """ Use the logger callback to log a message.

        Args:
            message (str): the message to be passed to the logger
        """

        if callable(cls._log_callback):
            cls._log_callback(message)

    @classmethod
    def _datetime(cls, dt = None):
        """ Access the RTC through the callback. This is a setter and getter function.

        Args:
            dt (tuple, None): None or 8-tuple(year, month, day, hours, minutes, seconds, weekday, subseconds)
                If None, the function acts as a getter. If a tuple, the function acts as a setter
        """

        if not callable(cls._datetime_callback):
            raise Exception('No callback set to access the RTC')

        if dt is None:
            return cls._datetime_callback()
        elif isinstance(dt, tuple) and len(dt) == 8:
            cls._datetime_callback(dt)
        else:
            raise ValueError(
                'Invalid parameter: dt={} must be a 8-tuple(year, month, day, hours, minutes, seconds, weekday, subseconds)'.format(dt))

    @staticmethod
    def _validate_host(host: str):
        """ Check if a host is valid. A host can be any valid hostname or IP address

        Args:
            host (str): hostname or IP address in dot notation to be validated

        Returns:
            bool: True on success, False on error
        """

        if Ntp._validate_ip(host) or Ntp._validate_hostname(host):
            return True

        return False

    @staticmethod
    def _validate_hostname(hostname: str):
        """ Check if a hostname is valid.

        Args:
            hostname (str): the hostname to be validated

        Returns:
            bool: True on success, False on error
        """

        if not isinstance(hostname, str):
            raise ValueError('Invalid parameter: hostname={} must be a string'.format(hostname))

        # strip exactly one dot from the right, if present
        if hostname[-1] == '.':
            hostname = hostname[:-1]

        if not (0 < len(hostname) <= 253):
            return False

        labels = hostname.split('.')

        # the TLD must be not all-numeric
        if re.match(r'[0-9]+$', labels[-1]):
            return False

        allowed = re.compile(r'^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9_\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9_\-]*[A-Za-z0-9])$')
        if not allowed.match(hostname):
            return False

        return True

    @staticmethod
    def _validate_ip(ip: str):
        """ Check if the IP is a valid IP address in dot notation

        Args:
            ip (str): the ip to be validated

        Returns:
            bool: True on success, False on error
        """

        if not isinstance(ip, str):
            raise ValueError('Invalid parameter: ip={} must be a string'.format(ip))

        allowed = re.compile(
            r'^(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)$')
        if allowed.match(ip) is None:
            return False

        return True

    @classmethod
    def _select_epoch(cls, epoch = None, epoch_list = None):
        """ Helper function to select an epoch from a given 3-tuple of epochs

        Args:
            epoch (int): epoch index to return
            epoch_list (tuple): a 3-tuple with the epochs. Each item in the tuple represents
                the seconds between year 2000 and the one that the item represents.

        Returns:
            int: the selected epoch
        """

        if epoch is None:
            epoch = cls.EPOCH_2000

        if epoch not in (cls.EPOCH_1900, cls.EPOCH_1970, cls.EPOCH_2000):
            raise ValueError('Invalid parameter: epoch={}'.format(epoch))

        if epoch_list is None:
            return (_NTP_DELTA_1900_2000, _NTP_DELTA_1970_2000, 0)[epoch]
        elif not isinstance(epoch_list, tuple) or len(epoch_list) != 3:
            raise ValueError('Invalid parameter: epoch_list={} must be a tuple and its length must be 3'.format(epoch_list))

        return epoch_list[epoch]
