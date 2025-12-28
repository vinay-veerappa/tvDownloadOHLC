
import pandas as pd
import pytz

def check_norm():
    tz = pytz.timezone('US/Eastern')
    idx = pd.to_datetime(['2021-01-04 09:30:00']).tz_localize('UTC').tz_convert(tz)
    print(f"Original Index: {idx[0]}")
    norm = idx.normalize()
    print(f"Normalized Index: {norm[0]}")
    d = norm[0]
    t930 = d + pd.Timedelta(hours=9, minutes=30)
    print(f"t930: {t930}")
    print(f"Equality Check: {idx[0] == t930}")

if __name__ == "__main__":
    check_norm()
