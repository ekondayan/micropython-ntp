# <u>micropython-ntp</u>

---

# <u>Description</u>

A robust MicroPython **Time library** for manipulating the **RTC** and and syncing it with **NTP**.

<u>Features:</u>

1. Sync the RTC from a list of NTP hosts

2. Multiple NTP hosts

3. Calculate and compensate RTC drift

4. Timezones

5. Epochs

6. Get time in sec, ms and us

7. Custom Logger with callback function

<u>Unfinished:</u>

1. Extra precision - take into account the time required to call the functions and compensate for that. Thist is a rather controversial feature, which may be not be implemented at all.

2. Day Light Saving Time

3. Robust host validation with regular expressions

*At this point all the implemented features are robustly tested and they seem stable enough for production.*

**RTC sync**

For syncing the RTC you have to set a list of hosts first and then run

```python
def rtc_sync(cls)
```

This function will try to read the time from the hosts list. The first available host will be used to set the time of the RTC in **UTC**. 

A timeout in seconds can be set when accessing the hosts

```python
def set_ntp_timeout(cls, timeout_s: int = 1)
```

**Reading the time**

To read the time, a set of functions are available

```python
def time_s(cls, epoch: int = None)
def time_ms(cls, epoch: int = None)
def time_us(cls, epoch: int = None)
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
def drift_calculate(cls)
```

Connects to the NTP server and returns the calculated ppm and the time in micro seconds, either positive or negative. Positive values represent a RTC that is speeding, negative values represent RTC that is lagging, when the value is zero, the RTC can be considered accurate. For this function to work, you have to sync the RTC first. My personal recommendation is to wait for at least 15 minutes after syncing the RTC and then to calculate the drifting. Longer time periods will give you more accurate value.

To calculate the drift at a latter stage, you can run

```python
def drift_us(cls, ppm_drift: float = None)
```

This function does not read the time from the NTP server(no internet connection is required), instead it uses the previously calculated ppm.

If you know in advance how much is the local RTC drifting, you can set it manually by calling

```python
def set_drift_ppm(cls, ppm: float)
```

The `ppm` parameter can be positive or negative. Positive values represent a RTC that is speeding, negative values represent RTC that is lagging.

Here is a list of all the functions that are managing the drift

```python
def drift_calculate(cls)
def drift_last_compensate(cls, epoch: int = None):
def drift_last_calculate(cls, epoch: int = None)
def drift_ppm(cls)
def set_drift_ppm(cls, ppm: float)
def drift_us(cls, ppm_drift: float = None)
def drift_compensate(cls, compensate_us: int)
```

**Timezones**

The library has support for timezones. Setting the timezone ensures basic correctness checks and sets the timezone. Just call

```python
def set_timezone(cls, hour: int, minute: int = 0)
```

**!!! NOTE: When syncing or compensating the RTC, the time will be set in UTC !!!**

When you get the time with

```python
def time_s(cls, epoch: int = None)
def time_ms(cls, epoch: int = None)
def time_us(cls, epoch: int = None)
```

the timezone will be calculated automatically.

**Logger**

The library support setting a custom logger. If you want to redirect the error messages to another destination, set your logger

```python
def set_logger(cls, callback = None)
```

The default logger is set to the function `print()`. To disable error logging, just set the callback to `None`.

# <u>Dependencies</u>

* Module sockets

* Module struct

* Module time

* Module re

* Module machine - from micropython

# <u>Download</u>

You can download the project from GitHub:

```bash
git clone https://github.com/ekondayan/micropython-ntp.git micropython-ntp
```

# <u>License</u>

This Source Code Form is subject to the BSD 3-Clause license. You can find it under  the LICENSE.md file in the projects' directory or here: [The 3-Clause BSD License](https://opensource.org/licenses/BSD-3-Clause)
