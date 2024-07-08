from datetime import datetime, timedelta

class TimeRange:
    def __init__(self, min_time: datetime=None, max_time: datetime=None):
        self.reference_date = datetime(2023, 1, 1)
        if min_time:
            self.minTime = int((min_time - self.reference_date).total_seconds())
        else:
            self.minTime = 0
        if max_time:
            self.maxTime = int((max_time - self.reference_date).total_seconds())
        else:
            self.maxTime = 0

    def set_minTime(self, new_min_time: datetime):
        self.minTime = int((new_min_time - self.reference_date).total_seconds())

    def set_maxTime(self, new_max_time: datetime):
        self.maxTime = int((new_max_time - self.reference_date).total_seconds())

    def addStamp(self, timestamp: datetime):
        timestamp_seconds = abs(int((timestamp - self.reference_date).total_seconds()))
        if timestamp_seconds < self.minTime or self.minTime == 0:
            self.minTime = timestamp_seconds
        elif timestamp_seconds > self.maxTime or self.maxTime== 0:
            self.maxTime = timestamp_seconds
    
    def addStamps(self, timestamps):
        for timestamp in timestamps:
            self.addStamp(timestamp) 

    def subset_of(self, other_time_range):
        if self.minTime <other_time_range.minTime or self.maxTime>other_time_range.maxTime:
            return False
        return True

    def compose(self, other_time_ranges):
        mins = [tr.minTime for tr in other_time_ranges]
        maxes = [tr.maxTime for tr in other_time_ranges]
        minimum = min(mins) if mins else 0
        maximum = max(maxes) if maxes else 0
        self.minTime = min(self.minTime, minimum) if self.minTime else minimum
        self.maxTime = max(self.maxTime, maximum) if self.maxTime else maximum

    def contains(self, timestamp):
        seconds = self.as_seconds(timestamp)
        if seconds<self.minTime or seconds>self.maxTime:
            return False
        return True
    
    def copy(self):
        return TimeRange(datetime.fromtimestamp(self.minTime + self.reference_date.timestamp()), 
                         datetime.fromtimestamp(self.maxTime + self.reference_date.timestamp()))

    def as_seconds(self, timestamp):
        return abs((self.reference_date-timestamp).total_seconds())
    
    def __eq__(self, other):
        return (self.minTime, self.maxTime) == (other.minTime, other.maxTime)

    def __ne__(self, other):
        return (self.minTime, self.maxTime) != (other.minTime, other.maxTime)

    def __lt__(self, other):
        return (self.minTime, self.maxTime) < (other.minTime, other.maxTime)

    def __le__(self, other):
        return (self.minTime, self.maxTime) <= (other.minTime, other.maxTime)

    def __gt__(self, other):
        return (self.minTime, self.maxTime) > (other.minTime, other.maxTime)

    def __ge__(self, other):
        return (self.minTime, self.maxTime) >= (other.minTime, other.maxTime)
    
    def __str__(self):
        min_time_str = (self.reference_date + timedelta(seconds=self.minTime)).strftime('%Y-%m-%d %H:%M:%S')
        max_time_str = (self.reference_date + timedelta(seconds=self.maxTime)).strftime('%Y-%m-%d %H:%M:%S')
        return f'TimeRange from {min_time_str} to {max_time_str}'

