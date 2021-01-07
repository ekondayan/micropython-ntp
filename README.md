# <u>micropython-ntp</u>

---

# <u>Description</u>

A robust MicroPython **Time library** for manipulating the **RTC** and and syncing it from a list of **NTP** servers.

<u>Features:</u>

1. Sync the RTC from a NTP host

2. Multiple NTP hosts

3. Microsecond precision

4. RTC chip-agnostic

5. Calculate and compensate RTC drift

6. Timezones

7. Epochs

8. Day Light Saving Time

9. Get time in sec, ms and us

10. Custom Logger with callback function

<u>Unfinished:</u>

1. Extra precision - take into account the time required to call the functions and compensate for that. This is a rather controversial feature, which may be not be implemented at all.

2. Robust host validation with regular expressions

3. Unit tests

***!!!At this point all the implemented features are robustly tested and they seem stable enough for production, BUT I do not recommended to use it in a production environment until the API stabilization phase is finished and some unit tests are developed.!!!***

**Initialize the library**

The first thing to do when using the library is to set a callback function for accessing the RTC chip. The idea behind this strategy is that the library can manipulate multiple RTC chips(internal, external or combination of both). 

The callback is a function in the form `func(datetime: tuple)`.

With no arguments, this method returns an 8-tuple with the current date and time. With 1 argument (being an 8-tuple) it sets the date and time.

The `datetime` tuple has the following format: `tuple(year, month, day, weekday, hours, minutes, seconds, subseconds)`

`weekday` is 1-7 for Monday through Sunday.

Micropython example:

```python
from machine import RTC
from ntp import Ntp

_rtc = RTC()
Ntp.set_datetime_callback(_rtc.datetime)
```

**RTC sync**

For syncing the RTC you have to set a list of hosts first and then run

```python
Ntp.rtc_sync()
```

This function will try to read the time from the hosts list. The first available host will be used to set the time of the RTC in **UTC**. 

A timeout in seconds can be set when accessing the hosts

```python
Ntp.set_ntp_timeout(timeout_s: int = 1)
```

**Reading the time**

To read the time, a set of functions are available

```python
Ntp.time_s(epoch: int = None)
Ntp.time_ms(epoch: int = None)
Ntp.time_us(epoch: int = None)
```

The suffix of each function shows how the time will be represented.

- **_s** - means seconds

- **_ms** - means milliseconds

- **_us** - means microseconds

See below, how to use epochs.

**Epochs**

Another nice feature is the ability to calculate the time according to a selected epoch. In micropython the default epoch is `2000-01-01 00:00:00 UTC`. When reading the time, you can pass

```python
Ntp.EPOCH_1900
Ntp.EPOCH_1970
Ntp.EPOCH_2000
```

as value to the `epoch` parameter and the returned time will be calculated according to the chosen epoch.

**RTC drift**

Compare the local RTC with the network time and calculate how much the local RTC is drifting. Calculating the drift is easily done by calling

```python
Ntp.drift_calculate()
```

Connects to the NTP server and returns the calculated ppm and the time in micro seconds, either positive or negative. Positive values represent a RTC that is speeding, negative values represent RTC that is lagging, when the value is zero, the RTC can be considered accurate. For this function to work, you have to sync the RTC first. My personal recommendation is to wait for at least 15 minutes after syncing the RTC and then to calculate the drifting. Longer time periods will give you more accurate value.

To calculate the drift at a latter stage, you can run

```python
Ntp.drift_us(ppm_drift: float = None)
```

This function does not read the time from the NTP server(no internet connection is required), instead it uses the previously calculated ppm.

If you know in advance how much is the local RTC drifting, you can set it manually by calling

```python
Ntp.set_drift_ppm(ppm: float)
```

The `ppm` parameter can be positive or negative. Positive values represent a RTC that is speeding, negative values represent RTC that is lagging.

Here is a list of all the functions that are managing the drift

```python
Ntp.drift_calculate(cls)
Ntp.drift_last_compensate(epoch: int = None):
Ntp.drift_last_calculate(epoch: int = None)
Ntp.drift_ppm(cls)
Ntp.set_drift_ppm(ppm: float)
Ntp.drift_us(ppm_drift: float = None)
Ntp.drift_compensate(compensate_us: int)
```

**Timezones**

The library has support for timezones. Setting the timezone ensures basic correctness checks and sets the timezone. Just call

```python
Ntp.set_timezone(hour: int, minute: int = 0)
```

**!!! NOTE: When syncing or compensating the RTC, the time will be set in UTC !!!**

When you get the time with

```python
Ntp.time_s(epoch: int = None)
Ntp.time_ms(epoch: int = None)
Ntp.time_us(epoch: int = None)
```

the timezone will be calculated automatically.

**Daylight Saving Time**

TODO

**Logger**

The library support setting a custom logger. If you want to redirect the error messages to another destination, set your logger

```python
Ntp.set_logger(callback = print)
```

The default logger is `print()` and to set it just call the method without any parameters.  To disable logging, set the callback to "None"

# <u>Dependencies</u>

* Module sockets

* Module struct

* Module time

* Module re

* 

# <u>Download</u>

You can download the project from GitHub:

```bash
git clone https://github.com/ekondayan/micropython-ntp.git micropython-ntp
```

# <u>License</u>

This Source Code Form is subject to the BSD 3-Clause license. You can find it under  the LICENSE.md file in the projects' directory or here: [The 3-Clause BSD License](https://opensource.org/licenses/BSD-3-Clause)
