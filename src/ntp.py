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

    _dst_start: dict
    _dst_end: dict
    _dst_bias: int

    @classmethod
    def set_dst_start(cls, month: int, week: int, dow: int):
        pass

    @classmethod
    def get_dst_start(cls):
        pass

    @classmethod
    def set_dst_end(cls, month: int, week: int, dow: int):
        pass

    @classmethod
    def get_dst_end(cls):
        pass

    @classmethod
    def set_dst_time_bias(cls, bias: int):
        pass

    @classmethod
    def get_dst_time_bias(cls):
        passs

    @classmethod
    def set_logger(cls, callback = None):
        if callback is None or callable(callback):
            cls._logger = callback
        else:
            raise Exception('Callback parameter must be a callable object or None to set it to print()')

    @classmethod
    def set_ntp_timeout(cls, timeout_s: int = 1):
        if not instance(timeout_s, int):
            raise Exception('Timeout parameter represents seconds in integer form')

        cls._ntp_timeout_s = timeout_s

    @classmethod
    def ntp_timeout(cls):
        return cls._ntp_timeout_s

    @classmethod
    def hosts(cls):
        return tuple(cls._hosts)

    @classmethod
    def set_hosts(cls, value: list):
        cls._hosts.clear()

        for host in value:
            if Ntp.validate_hostname(host):
                cls._hosts.append(host)

    @classmethod
    def timezone(cls):
        return cls._timezone // 3600, (cls._timezone % 3600) // 60

    @classmethod
    def set_timezone(cls, hour: int, minute: int = 0):
        if (
                (minute == 0 and not (-12 <= hour <= 12)) or
                (minute == 30 and hour not in (-9, -3, 3, 4, 5, 6, 9, 10)) or
                (minute == 45 and hour not in (5, 8, 12))
        ):
            raise Exception('Timezone is invalid')

        cls._timezone = hour * 3600 + minute * 60

    @classmethod
    def time_s(cls, epoch: int = None):
        return cls.time_us(epoch) // 1000000

    @classmethod
    def time_ms(cls, epoch: int = None):
        return cls.time_us(epoch) // 1000

    @classmethod
    def time_us(cls, epoch: int = None):
        epoch = cls._normalize_epoch(epoch, (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0))
        dst = 0

        # Do not take the value when on the verge of the next second
        # This is required to ensure that the sec and usec will be read within the boundaries of one second
        us = cls._rtc.datetime()[7]
        if us >= 995000:
            time.sleep_us(100000 - us)

        return (time.time() + epoch + cls._timezone + dst) * 1000000 + cls._rtc.datetime()[7]

    @classmethod
    def network_time(cls, epoch = None):
        if not any(cls._hosts):
            raise Exception('There are no valid Hostnames/IPs set for the time server')

        epoch = cls._normalize_epoch(epoch, (0, cls._NTP_DELTA_1900_1970, cls._NTP_DELTA_1900_2000))
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
        ntp_reading = cls.network_time(cls.EPOCH_2000)

        # Negate the execution time of all the instructions up to this point
        ntp_us = ntp_reading[0] + (time.ticks_us() - ntp_reading[1])
        lt = time.localtime(ntp_us // 1000000)
        cls._rtc.datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], ntp_us % 1000000))
        cls._rtc_last_sync = ntp_us

    @classmethod
    def rtc_last_sync(cls, epoch: int = None):
        epoch = cls._normalize_epoch(epoch, (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0))
        return cls._rtc_last_sync + epoch * 1000000

    @classmethod
    def drift_calculate(cls):
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
        epoch = cls._normalize_epoch(epoch, (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0))
        return cls._drift_last_compensate + epoch * 1000000

    @classmethod
    def drift_last_calculate(cls, epoch: int = None):
        epoch = cls._normalize_epoch(epoch, (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0))
        return cls._drift_last_calculate + epoch * 1000000

    @classmethod
    def drift_ppm(cls):
        return cls._ppm_drift

    @classmethod
    def set_drift_ppm(cls, ppm: float):
        if not isinstance(ppm, (float, int)):
            raise Exception('ppm parameter must be float or int')
        cls._ppm_drift = float(ppm)

    @classmethod
    def drift_us(cls, ppm_drift: float = None):
        if cls._rtc_last_sync == 0 and cls._drift_last_compensate == 0:
            return 0

        if ppm_drift is None:
            ppm_drift = cls._ppm_drift

        delta_time_rtc = cls.time_us(cls.EPOCH_2000) - max(cls._rtc_last_sync, cls._drift_last_compensate)
        delta_time_real = (1000000 * delta_time_rtc) // (1000000 + ppm_drift)

        return delta_time_rtc - delta_time_real

    @classmethod
    def drift_compensate(cls, compensate_us: int):
        rtc_us = cls.time_us(Ntp.EPOCH_2000)
        rtc_us += compensate_us
        lt = time.localtime(rtc_us // 1000000)
        cls._rtc.datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], rtc_us % 1000000))
        cls._drift_last_compensate = rtc_us

    @staticmethod
    def validate_hostname(hostname: str):
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
    def _normalize_epoch(cls, epoch, epoch_list):
        if not isinstance(epoch_list, tuple):
            raise Exception('Invalid parameter: epoch_list must be a tuple')

        if isinstance(epoch, int) and epoch in (0, 1, 2):
            return epoch_list[epoch]
        elif epoch is None:
            return 0
        else:
            raise Exception('Invalid parameter: epoch')

    @classmethod
    def _log(cls, message: str):
        if callable(cls._logger):
            cls._logger(message)
