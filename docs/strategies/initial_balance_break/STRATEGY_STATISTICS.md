# IB Strategy Statistics — Comprehensive Report

**Generated:** 2026-07-25  
**Symbols:** NQ1, ES1, YM1, RTY1, CL1, GC1


## 1. Empirical Baselines (No-Filter Reference)

These are the reference win rates every filter's lift is measured against.


### TrevorTrades 10-Year ES Priors

| Metric | Value |
|---|---|
| High Breakout Rate | 0.671 |
| Low Breakout Rate | 0.724 |
| Both Breached Rate | 0.401 |
| Contained Rate | 0.006 |
| Above Mid Then High Break | 0.835 |
| Below Mid Then Low Break | 0.949 |
| Ext 25 Hit | 0.853 |
| Ext 50 Hit | 0.695 |
| Ext 100 Hit | 0.445 |
| Breaks In First 30Min | 0.841 |
| Breaks In First 60Min | 0.918 |
| Avg First Breakout Min | 18 |
| Median First Breakout Min | 2 |


### Per-Symbol Baselines (from this pipeline)


**NQ1:**

| Target | Baseline WR |
|---|---|
| play1_result | 0.2885 |
| play2_result | 0.0991 |
| play3_result | 0.1367 |
| bias_correct_combined_05x | 0.342 |
| realized_dir_break | 0.4747 |


## 2. Overall Strategy Statistics by Symbol


### NQ1 — Overall (all sessions, all target levels)

| Play | N | Win Rate | Expectancy (R) | Profit Factor | Avg MFE | Avg MAE | Wins | Losses |
|---|---|---|---|---|---|---|---|---|
| Play 1 — IB Breakout | 166016 | 0.473 | 0.0875 | 1.1229 | 0.0833 | 0.076 | 78531 | 69833 |
| Play 2 — IB Retest | 166016 | 0.0917 | 0.0168 | 0.6353 | 0.0393 | 0.0298 | 15221 | 59395 |
| Play 3 — IB Fade | 166016 | 0.1237 | 0.0276 | 1.0861 | 0.0183 | 0.0163 | 20538 | 25171 |


### NQ1 — By Session

| Session | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| NY AM IB | Play 1 — IB Breakout | 21112 | 0.4635 | 0.0597 | 0.9124 |
| NY AM IB | Play 2 — IB Retest | 21112 | 0.0604 | -0.0177 | 0.383 |
| NY AM IB | Play 3 — IB Fade | 21112 | 0.116 | 0.0206 | 1.0092 |
| NY PM IB | Play 1 — IB Breakout | 20440 | 0.447 | 0.0706 | 0.9469 |
| NY PM IB | Play 2 — IB Retest | 20440 | 0.0589 | 0.0215 | 0.4029 |
| NY PM IB | Play 3 — IB Fade | 20440 | 0.1194 | 0.033 | 1.1087 |
| London IB | Play 1 — IB Breakout | 42064 | 0.3805 | 0.0769 | 0.9968 |
| London IB | Play 2 — IB Retest | 42064 | 0.0302 | 0.009 | 0.3195 |
| London IB | Play 3 — IB Fade | 42064 | 0.0768 | 0.0194 | 0.9156 |
| Globex IB | Play 1 — IB Breakout | 20684 | 0.2266 | 0.0566 | 0.8434 |
| Globex IB | Play 2 — IB Retest | 20684 | 0.0098 | 0.0018 | 0.2293 |
| Globex IB | Play 3 — IB Fade | 20684 | 0.0363 | 0.0131 | 0.7805 |
| Tokyo IB | Play 1 — IB Breakout | 41080 | 0.5837 | 0.1103 | 1.2769 |
| Tokyo IB | Play 2 — IB Retest | 41080 | 0.118 | 0.0199 | 0.6477 |
| Tokyo IB | Play 3 — IB Fade | 41080 | 0.1617 | 0.0326 | 1.1659 |
| Midnight OR | Play 1 — IB Breakout | 20636 | 0.7238 | 0.1401 | 1.5072 |
| Midnight OR | Play 2 — IB Retest | 20636 | 0.3112 | 0.0721 | 1.1205 |
| Midnight OR | Play 3 — IB Fade | 20636 | 0.2435 | 0.0502 | 1.2965 |


### NQ1 — By Target Level (extension multiplier)

| Play | Target | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Play 1 — IB Breakout | 0.25x | 41504 | 0.7103 | 0.0798 | 1.746 |
| Play 1 — IB Breakout | 0.5x | 41504 | 0.5184 | 0.0884 | 1.3037 |
| Play 1 — IB Breakout | 0.75x | 41504 | 0.3749 | 0.0852 | 1.0321 |
| Play 1 — IB Breakout | 1.0x | 41504 | 0.2885 | 0.0968 | 0.8919 |
| Play 2 — IB Retest | 0.25x | 41504 | 0.1358 | 0.0171 | 0.8156 |
| Play 2 — IB Retest | 0.5x | 41504 | 0.0991 | 0.0181 | 0.6903 |
| Play 2 — IB Retest | 0.75x | 41504 | 0.0736 | 0.0152 | 0.577 |
| Play 2 — IB Retest | 1.0x | 41504 | 0.0583 | 0.0168 | 0.5117 |
| Play 3 — IB Fade | 0.25x | 41504 | 0.1112 | 0.0569 | 1.1309 |
| Play 3 — IB Fade | 0.5x | 41504 | 0.1367 | 0.0277 | 1.057 |
| Play 3 — IB Fade | 0.75x | 41504 | 0.1305 | 0.0164 | 1.0517 |
| Play 3 — IB Fade | 1.0x | 41504 | 0.1164 | 0.0092 | 1.0464 |


### NQ1 — By Year

| Year | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| 2006 | Play 1 — IB Breakout | 6812 | 0.5263 | 0.1537 | 1.5639 |
| 2006 | Play 2 — IB Retest | 6812 | 0.0871 | 0.0266 | 0.7038 |
| 2006 | Play 3 — IB Fade | 6812 | 0.123 | 0.006 | 0.9103 |
| 2007 | Play 1 — IB Breakout | 7504 | 0.5124 | 0.1123 | 1.2803 |
| 2007 | Play 2 — IB Retest | 7504 | 0.1138 | 0.0699 | 0.8431 |
| 2007 | Play 3 — IB Fade | 7504 | 0.1373 | 0.0246 | 1.0728 |
| 2008 | Play 1 — IB Breakout | 8036 | 0.51 | 0.0701 | 1.0788 |
| 2008 | Play 2 — IB Retest | 8036 | 0.1022 | 0.0078 | 0.6373 |
| 2008 | Play 3 — IB Fade | 8036 | 0.1384 | 0.0376 | 1.1936 |
| 2009 | Play 1 — IB Breakout | 8104 | 0.4604 | 0.0553 | 0.9882 |
| 2009 | Play 2 — IB Retest | 8104 | 0.0876 | -0.0221 | 0.5841 |
| 2009 | Play 3 — IB Fade | 8104 | 0.1354 | 0.0385 | 1.1371 |
| 2010 | Play 1 — IB Breakout | 8184 | 0.4973 | 0.1049 | 1.2031 |
| 2010 | Play 2 — IB Retest | 8184 | 0.0953 | 0.0225 | 0.6512 |
| 2010 | Play 3 — IB Fade | 8184 | 0.1241 | 0.0211 | 1.0194 |
| 2011 | Play 1 — IB Breakout | 8172 | 0.4841 | 0.0934 | 1.1397 |
| 2011 | Play 2 — IB Retest | 8172 | 0.0882 | 0.0068 | 0.586 |
| 2011 | Play 3 — IB Fade | 8172 | 0.1192 | 0.0099 | 0.9465 |
| 2012 | Play 1 — IB Breakout | 8144 | 0.4889 | 0.0944 | 1.1582 |
| 2012 | Play 2 — IB Retest | 8144 | 0.0873 | 0.0044 | 0.5686 |
| 2012 | Play 3 — IB Fade | 8144 | 0.1272 | 0.0143 | 0.9803 |
| 2013 | Play 1 — IB Breakout | 8052 | 0.464 | 0.0795 | 1.1145 |
| 2013 | Play 2 — IB Retest | 8052 | 0.1089 | 0.0519 | 0.7669 |
| 2013 | Play 3 — IB Fade | 8052 | 0.1315 | 0.0365 | 1.1669 |
| 2014 | Play 1 — IB Breakout | 7992 | 0.4812 | 0.1106 | 1.2775 |
| 2014 | Play 2 — IB Retest | 7992 | 0.0862 | 0.0111 | 0.6353 |
| 2014 | Play 3 — IB Fade | 7992 | 0.1171 | 0.012 | 0.9629 |
| 2015 | Play 1 — IB Breakout | 8220 | 0.4637 | 0.0875 | 1.1124 |
| 2015 | Play 2 — IB Retest | 8220 | 0.1001 | 0.0364 | 0.708 |
| 2015 | Play 3 — IB Fade | 8220 | 0.1131 | 0.0226 | 1.0792 |
| 2016 | Play 1 — IB Breakout | 8204 | 0.4334 | 0.0542 | 0.9775 |
| 2016 | Play 2 — IB Retest | 8204 | 0.0896 | 0.0059 | 0.6297 |
| 2016 | Play 3 — IB Fade | 8204 | 0.1238 | 0.0465 | 1.2624 |
| 2017 | Play 1 — IB Breakout | 8192 | 0.4489 | 0.084 | 1.1135 |
| 2017 | Play 2 — IB Retest | 8192 | 0.078 | 0.0165 | 0.59 |
| 2017 | Play 3 — IB Fade | 8192 | 0.1207 | 0.0242 | 1.0484 |
| 2018 | Play 1 — IB Breakout | 8212 | 0.4793 | 0.0865 | 1.1318 |
| 2018 | Play 2 — IB Retest | 8212 | 0.0867 | 0.0047 | 0.592 |
| 2018 | Play 3 — IB Fade | 8212 | 0.1247 | 0.0243 | 1.0649 |
| 2019 | Play 1 — IB Breakout | 8216 | 0.4664 | 0.0873 | 1.0911 |
| 2019 | Play 2 — IB Retest | 8216 | 0.0901 | 0.004 | 0.6165 |
| 2019 | Play 3 — IB Fade | 8216 | 0.124 | 0.0314 | 1.1251 |
| 2020 | Play 1 — IB Breakout | 8248 | 0.4681 | 0.0791 | 1.0761 |
| 2020 | Play 2 — IB Retest | 8248 | 0.0897 | -0.0075 | 0.5939 |
| 2020 | Play 3 — IB Fade | 8248 | 0.1235 | 0.0336 | 1.2032 |
| 2021 | Play 1 — IB Breakout | 8248 | 0.4578 | 0.0959 | 1.1382 |
| 2021 | Play 2 — IB Retest | 8248 | 0.0869 | 0.0293 | 0.6125 |
| 2021 | Play 3 — IB Fade | 8248 | 0.1137 | 0.0291 | 1.1475 |
| 2022 | Play 1 — IB Breakout | 8204 | 0.4549 | 0.0735 | 1.0177 |
| 2022 | Play 2 — IB Retest | 8204 | 0.083 | 0.0078 | 0.5739 |
| 2022 | Play 3 — IB Fade | 8204 | 0.1164 | 0.0379 | 1.1424 |
| 2023 | Play 1 — IB Breakout | 8208 | 0.4637 | 0.0864 | 1.0906 |
| 2023 | Play 2 — IB Retest | 8208 | 0.0994 | 0.0444 | 0.7031 |
| 2023 | Play 3 — IB Fade | 8208 | 0.1223 | 0.0355 | 1.1123 |
| 2024 | Play 1 — IB Breakout | 8248 | 0.4565 | 0.079 | 1.0752 |
| 2024 | Play 2 — IB Retest | 8248 | 0.0855 | 0.0064 | 0.5831 |
| 2024 | Play 3 — IB Fade | 8248 | 0.1208 | 0.0252 | 1.092 |
| 2025 | Play 1 — IB Breakout | 8196 | 0.4519 | 0.0819 | 1.072 |
| 2025 | Play 2 — IB Retest | 8196 | 0.0888 | 0.0284 | 0.6201 |
| 2025 | Play 3 — IB Fade | 8196 | 0.1193 | 0.0387 | 1.1293 |
| 2026 | Play 1 — IB Breakout | 4620 | 0.4816 | 0.0778 | 1.0696 |
| 2026 | Play 2 — IB Retest | 4620 | 0.0929 | -0.0067 | 0.5754 |
| 2026 | Play 3 — IB Fade | 4620 | 0.1238 | 0.0234 | 1.0716 |


### NQ1 — By Month (aggregated across all years)

| Month | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Jan | Play 1 — IB Breakout | 13588 | 0.4838 | 0.0978 | 1.1885 |
| Jan | Play 2 — IB Retest | 13588 | 0.0985 | 0.0426 | 0.7201 |
| Jan | Play 3 — IB Fade | 13588 | 0.1185 | 0.0231 | 1.06 |
| Feb | Play 1 — IB Breakout | 13228 | 0.4716 | 0.0791 | 1.0678 |
| Feb | Play 2 — IB Retest | 13228 | 0.0942 | 0.0135 | 0.6393 |
| Feb | Play 3 — IB Fade | 13228 | 0.1272 | 0.0283 | 1.0877 |
| Mar | Play 1 — IB Breakout | 14312 | 0.4792 | 0.0861 | 1.1073 |
| Mar | Play 2 — IB Retest | 14312 | 0.1004 | 0.0281 | 0.6907 |
| Mar | Play 3 — IB Fade | 14312 | 0.1281 | 0.0297 | 1.1142 |
| Apr | Play 1 — IB Breakout | 13728 | 0.4738 | 0.0871 | 1.1442 |
| Apr | Play 2 — IB Retest | 13728 | 0.0914 | 0.0145 | 0.6164 |
| Apr | Play 3 — IB Fade | 13728 | 0.1265 | 0.0342 | 1.1437 |
| May | Play 1 — IB Breakout | 14588 | 0.4566 | 0.0703 | 1.0374 |
| May | Play 2 — IB Retest | 14588 | 0.0879 | -0.0011 | 0.5958 |
| May | Play 3 — IB Fade | 14588 | 0.1219 | 0.032 | 1.1319 |
| Jun | Play 1 — IB Breakout | 14156 | 0.4759 | 0.085 | 1.1139 |
| Jun | Play 2 — IB Retest | 14156 | 0.0906 | 0.0018 | 0.6149 |
| Jun | Play 3 — IB Fade | 14156 | 0.1218 | 0.0241 | 1.0777 |
| Jul | Play 1 — IB Breakout | 14316 | 0.4693 | 0.0836 | 1.1077 |
| Jul | Play 2 — IB Retest | 14316 | 0.0932 | 0.0221 | 0.6267 |
| Jul | Play 3 — IB Fade | 14316 | 0.1245 | 0.0326 | 1.1271 |
| Aug | Play 1 — IB Breakout | 14044 | 0.4667 | 0.092 | 1.158 |
| Aug | Play 2 — IB Retest | 14044 | 0.0856 | 0.0147 | 0.5987 |
| Aug | Play 3 — IB Fade | 14044 | 0.128 | 0.0327 | 1.1338 |
| Sep | Play 1 — IB Breakout | 13452 | 0.4765 | 0.1004 | 1.1847 |
| Sep | Play 2 — IB Retest | 13452 | 0.092 | 0.0251 | 0.6789 |
| Sep | Play 3 — IB Fade | 13452 | 0.1201 | 0.0214 | 1.0131 |
| Oct | Play 1 — IB Breakout | 14024 | 0.4693 | 0.0808 | 1.0837 |
| Oct | Play 2 — IB Retest | 14024 | 0.0911 | 0.0137 | 0.6096 |
| Oct | Play 3 — IB Fade | 14024 | 0.1271 | 0.0314 | 1.1249 |
| Nov | Play 1 — IB Breakout | 13400 | 0.4819 | 0.0954 | 1.1559 |
| Nov | Play 2 — IB Retest | 13400 | 0.0946 | 0.0269 | 0.6483 |
| Nov | Play 3 — IB Fade | 13400 | 0.1276 | 0.0327 | 1.1309 |
| Dec | Play 1 — IB Breakout | 13180 | 0.4732 | 0.095 | 1.1488 |
| Dec | Play 2 — IB Retest | 13180 | 0.0805 | 0.0005 | 0.5915 |
| Dec | Play 3 — IB Fade | 13180 | 0.1127 | 0.0068 | 0.896 |


### NQ1 — By Day of Week

| Day | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Thu | Play 1 — IB Breakout | 33660 | 0.4768 | 0.0798 | 1.0814 |
| Thu | Play 2 — IB Retest | 33660 | 0.0885 | -0.0026 | 0.5968 |
| Thu | Play 3 — IB Fade | 33660 | 0.1302 | 0.0355 | 1.1826 |
| Fri | Play 1 — IB Breakout | 33012 | 0.4778 | 0.0928 | 1.1605 |
| Fri | Play 2 — IB Retest | 33012 | 0.0951 | 0.0223 | 0.6598 |
| Fri | Play 3 — IB Fade | 33012 | 0.1212 | 0.0188 | 1.0 |
| Mon | Play 1 — IB Breakout | 31876 | 0.4446 | 0.0844 | 1.0928 |
| Mon | Play 2 — IB Retest | 31876 | 0.0844 | 0.0298 | 0.6287 |
| Mon | Play 3 — IB Fade | 31876 | 0.1142 | 0.0289 | 1.0723 |
| Tue | Play 1 — IB Breakout | 33756 | 0.4844 | 0.0956 | 1.1671 |
| Tue | Play 2 — IB Retest | 33756 | 0.0956 | 0.0243 | 0.6587 |
| Tue | Play 3 — IB Fade | 33756 | 0.1248 | 0.0259 | 1.0714 |
| Wed | Play 1 — IB Breakout | 33712 | 0.4801 | 0.0851 | 1.1136 |
| Wed | Play 2 — IB Retest | 33712 | 0.0945 | 0.011 | 0.6328 |
| Wed | Play 3 — IB Fade | 33712 | 0.1276 | 0.0287 | 1.1078 |


### ES1 — Overall (all sessions, all target levels)

| Play | N | Win Rate | Expectancy (R) | Profit Factor | Avg MFE | Avg MAE | Wins | Losses |
|---|---|---|---|---|---|---|---|---|
| Play 1 — IB Breakout | 165948 | 0.4845 | 0.1004 | 1.1962 | 0.0899 | 0.0794 | 80396 | 67076 |
| Play 2 — IB Retest | 165948 | 0.0972 | 0.0203 | 0.6583 | 0.0447 | 0.0324 | 16128 | 60288 |
| Play 3 — IB Fade | 165948 | 0.1283 | 0.0058 | 0.9266 | 0.0206 | 0.0207 | 21297 | 29558 |


### ES1 — By Session

| Session | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| NY AM IB | Play 1 — IB Breakout | 21088 | 0.5214 | 0.0732 | 1.0257 |
| NY AM IB | Play 2 — IB Retest | 21088 | 0.0819 | -0.017 | 0.4789 |
| NY AM IB | Play 3 — IB Fade | 21088 | 0.1362 | 0.0056 | 0.9392 |
| NY PM IB | Play 1 — IB Breakout | 20408 | 0.4756 | 0.0803 | 1.0228 |
| NY PM IB | Play 2 — IB Retest | 20408 | 0.0714 | 0.0281 | 0.4724 |
| NY PM IB | Play 3 — IB Fade | 20408 | 0.129 | 0.0298 | 1.0949 |
| London IB | Play 1 — IB Breakout | 42000 | 0.376 | 0.0861 | 1.0335 |
| London IB | Play 2 — IB Retest | 42000 | 0.0275 | 0.0084 | 0.3086 |
| London IB | Play 3 — IB Fade | 42000 | 0.0761 | 0.0038 | 0.788 |
| Globex IB | Play 1 — IB Breakout | 20676 | 0.2339 | 0.0693 | 0.9385 |
| Globex IB | Play 2 — IB Retest | 20676 | 0.0133 | 0.0098 | 0.2839 |
| Globex IB | Play 3 — IB Fade | 20676 | 0.0406 | -0.0008 | 0.6803 |
| Tokyo IB | Play 1 — IB Breakout | 41140 | 0.5744 | 0.1149 | 1.2966 |
| Tokyo IB | Play 2 — IB Retest | 41140 | 0.116 | 0.0242 | 0.6423 |
| Tokyo IB | Play 3 — IB Fade | 41140 | 0.161 | 0.0003 | 0.9416 |
| Midnight OR | Play 1 — IB Breakout | 20636 | 0.7479 | 0.1792 | 1.7107 |
| Midnight OR | Play 2 — IB Retest | 20636 | 0.3265 | 0.0775 | 1.125 |
| Midnight OR | Play 3 — IB Fade | 20636 | 0.2487 | 0.0038 | 1.0175 |


### ES1 — By Target Level (extension multiplier)

| Play | Target | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Play 1 — IB Breakout | 0.25x | 41487 | 0.7264 | 0.0946 | 2.0092 |
| Play 1 — IB Breakout | 0.5x | 41487 | 0.5328 | 0.1042 | 1.4086 |
| Play 1 — IB Breakout | 0.75x | 41487 | 0.3809 | 0.0935 | 1.0671 |
| Play 1 — IB Breakout | 1.0x | 41487 | 0.2978 | 0.1093 | 0.9452 |
| Play 2 — IB Retest | 0.25x | 41487 | 0.1452 | 0.0285 | 0.8603 |
| Play 2 — IB Retest | 0.5x | 41487 | 0.1066 | 0.0261 | 0.7315 |
| Play 2 — IB Retest | 0.75x | 41487 | 0.0749 | 0.0086 | 0.5685 |
| Play 2 — IB Retest | 1.0x | 41487 | 0.0621 | 0.0178 | 0.5352 |
| Play 3 — IB Fade | 0.25x | 41487 | 0.1112 | 0.0182 | 0.9554 |
| Play 3 — IB Fade | 0.5x | 41487 | 0.1426 | 0.002 | 0.8981 |
| Play 3 — IB Fade | 0.75x | 41487 | 0.137 | 0.0044 | 0.9338 |
| Play 3 — IB Fade | 1.0x | 41487 | 0.1226 | -0.0014 | 0.8849 |


### ES1 — By Year

| Year | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| 2006 | Play 1 — IB Breakout | 6820 | 0.5205 | 0.1637 | 1.6218 |
| 2006 | Play 2 — IB Retest | 6820 | 0.0968 | 0.0495 | 0.7283 |
| 2006 | Play 3 — IB Fade | 6820 | 0.1306 | -0.0303 | 0.7331 |
| 2007 | Play 1 — IB Breakout | 7512 | 0.5238 | 0.1509 | 1.5555 |
| 2007 | Play 2 — IB Retest | 7512 | 0.0969 | 0.0085 | 0.6664 |
| 2007 | Play 3 — IB Fade | 7512 | 0.1249 | -0.0344 | 0.7141 |
| 2008 | Play 1 — IB Breakout | 8048 | 0.5101 | 0.087 | 1.1416 |
| 2008 | Play 2 — IB Retest | 8048 | 0.1092 | 0.0024 | 0.6881 |
| 2008 | Play 3 — IB Fade | 8048 | 0.1363 | 0.0032 | 0.9385 |
| 2009 | Play 1 — IB Breakout | 8104 | 0.4783 | 0.0764 | 1.0954 |
| 2009 | Play 2 — IB Retest | 8104 | 0.1037 | 0.0173 | 0.6393 |
| 2009 | Play 3 — IB Fade | 8104 | 0.1426 | 0.0184 | 1.0138 |
| 2010 | Play 1 — IB Breakout | 8184 | 0.5161 | 0.1284 | 1.3327 |
| 2010 | Play 2 — IB Retest | 8184 | 0.0984 | 0.0256 | 0.6669 |
| 2010 | Play 3 — IB Fade | 8184 | 0.1321 | -0.0169 | 0.7997 |
| 2011 | Play 1 — IB Breakout | 8168 | 0.5016 | 0.1189 | 1.2724 |
| 2011 | Play 2 — IB Retest | 8168 | 0.1047 | 0.0372 | 0.7082 |
| 2011 | Play 3 — IB Fade | 8168 | 0.1322 | -0.0117 | 0.818 |
| 2012 | Play 1 — IB Breakout | 8144 | 0.4999 | 0.1132 | 1.2564 |
| 2012 | Play 2 — IB Retest | 8144 | 0.1027 | 0.0362 | 0.6419 |
| 2012 | Play 3 — IB Fade | 8144 | 0.1373 | -0.0066 | 0.8537 |
| 2013 | Play 1 — IB Breakout | 8116 | 0.4717 | 0.0916 | 1.1843 |
| 2013 | Play 2 — IB Retest | 8116 | 0.0954 | 0.0239 | 0.6213 |
| 2013 | Play 3 — IB Fade | 8116 | 0.1349 | -0.008 | 0.869 |
| 2014 | Play 1 — IB Breakout | 8008 | 0.4954 | 0.1268 | 1.3933 |
| 2014 | Play 2 — IB Retest | 8008 | 0.1033 | 0.0452 | 0.7352 |
| 2014 | Play 3 — IB Fade | 8008 | 0.1229 | -0.0167 | 0.7948 |
| 2015 | Play 1 — IB Breakout | 8220 | 0.4853 | 0.1134 | 1.3044 |
| 2015 | Play 2 — IB Retest | 8220 | 0.1096 | 0.0659 | 0.8206 |
| 2015 | Play 3 — IB Fade | 8220 | 0.1217 | 0.0052 | 0.9044 |
| 2016 | Play 1 — IB Breakout | 8212 | 0.4575 | 0.0776 | 1.1016 |
| 2016 | Play 2 — IB Retest | 8212 | 0.0984 | 0.0217 | 0.6697 |
| 2016 | Play 3 — IB Fade | 8212 | 0.1258 | 0.0135 | 0.9771 |
| 2017 | Play 1 — IB Breakout | 8192 | 0.4626 | 0.1019 | 1.2585 |
| 2017 | Play 2 — IB Retest | 8192 | 0.0918 | 0.0241 | 0.7058 |
| 2017 | Play 3 — IB Fade | 8192 | 0.1241 | -0.0085 | 0.8395 |
| 2018 | Play 1 — IB Breakout | 8212 | 0.4904 | 0.0883 | 1.1329 |
| 2018 | Play 2 — IB Retest | 8212 | 0.0924 | -0.0053 | 0.5952 |
| 2018 | Play 3 — IB Fade | 8212 | 0.1352 | 0.015 | 0.9888 |
| 2019 | Play 1 — IB Breakout | 8216 | 0.4686 | 0.0805 | 1.066 |
| 2019 | Play 2 — IB Retest | 8216 | 0.0914 | -0.005 | 0.5941 |
| 2019 | Play 3 — IB Fade | 8216 | 0.1344 | 0.0279 | 1.087 |
| 2020 | Play 1 — IB Breakout | 8248 | 0.4831 | 0.087 | 1.1082 |
| 2020 | Play 2 — IB Retest | 8248 | 0.0931 | -0.0042 | 0.6261 |
| 2020 | Play 3 — IB Fade | 8248 | 0.1171 | 0.0313 | 1.1525 |
| 2021 | Play 1 — IB Breakout | 8248 | 0.4667 | 0.0892 | 1.093 |
| 2021 | Play 2 — IB Retest | 8248 | 0.0815 | -0.0089 | 0.5671 |
| 2021 | Play 3 — IB Fade | 8248 | 0.1205 | 0.0197 | 1.0277 |
| 2022 | Play 1 — IB Breakout | 8204 | 0.4673 | 0.0708 | 1.0324 |
| 2022 | Play 2 — IB Retest | 8204 | 0.0841 | -0.0222 | 0.5641 |
| 2022 | Play 3 — IB Fade | 8204 | 0.1251 | 0.0265 | 1.1051 |
| 2023 | Play 1 — IB Breakout | 8212 | 0.4709 | 0.0908 | 1.1247 |
| 2023 | Play 2 — IB Retest | 8212 | 0.1097 | 0.0722 | 0.7301 |
| 2023 | Play 3 — IB Fade | 8212 | 0.1341 | 0.0272 | 1.0529 |
| 2024 | Play 1 — IB Breakout | 8248 | 0.4715 | 0.0771 | 1.0715 |
| 2024 | Play 2 — IB Retest | 8248 | 0.0976 | 0.0032 | 0.6344 |
| 2024 | Play 3 — IB Fade | 8248 | 0.1278 | 0.0171 | 1.0124 |
| 2025 | Play 1 — IB Breakout | 8196 | 0.4647 | 0.0886 | 1.1168 |
| 2025 | Play 2 — IB Retest | 8196 | 0.0887 | 0.0115 | 0.6342 |
| 2025 | Play 3 — IB Fade | 8196 | 0.1153 | 0.019 | 0.9821 |
| 2026 | Play 1 — IB Breakout | 4436 | 0.4727 | 0.1023 | 1.2043 |
| 2026 | Play 2 — IB Retest | 4436 | 0.0879 | 0.0409 | 0.62 |
| 2026 | Play 3 — IB Fade | 4436 | 0.1143 | 0.032 | 1.1139 |


### ES1 — By Month (aggregated across all years)

| Month | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Jan | Play 1 — IB Breakout | 13616 | 0.4934 | 0.1081 | 1.2551 |
| Jan | Play 2 — IB Retest | 13616 | 0.0934 | 0.0158 | 0.6517 |
| Jan | Play 3 — IB Fade | 13616 | 0.1233 | -0.0054 | 0.8597 |
| Feb | Play 1 — IB Breakout | 13228 | 0.4859 | 0.0904 | 1.1524 |
| Feb | Play 2 — IB Retest | 13228 | 0.0927 | -0.0034 | 0.5944 |
| Feb | Play 3 — IB Fade | 13228 | 0.1328 | 0.007 | 0.9368 |
| Mar | Play 1 — IB Breakout | 14208 | 0.4973 | 0.1073 | 1.2296 |
| Mar | Play 2 — IB Retest | 14208 | 0.1054 | 0.0294 | 0.7061 |
| Mar | Play 3 — IB Fade | 14208 | 0.1278 | 0.0012 | 0.9081 |
| Apr | Play 1 — IB Breakout | 13708 | 0.4807 | 0.0969 | 1.2007 |
| Apr | Play 2 — IB Retest | 13708 | 0.0924 | 0.0073 | 0.6323 |
| Apr | Play 3 — IB Fade | 13708 | 0.1307 | 0.0076 | 0.9447 |
| May | Play 1 — IB Breakout | 14516 | 0.4682 | 0.0869 | 1.1243 |
| May | Play 2 — IB Retest | 14516 | 0.0941 | 0.0052 | 0.6322 |
| May | Play 3 — IB Fade | 14516 | 0.1221 | 0.0082 | 0.9375 |
| Jun | Play 1 — IB Breakout | 14148 | 0.4786 | 0.0964 | 1.1844 |
| Jun | Play 2 — IB Retest | 14148 | 0.1019 | 0.0372 | 0.6874 |
| Jun | Play 3 — IB Fade | 14148 | 0.1292 | 0.0078 | 0.9621 |
| Jul | Play 1 — IB Breakout | 14392 | 0.4852 | 0.1021 | 1.2053 |
| Jul | Play 2 — IB Retest | 14392 | 0.098 | 0.0212 | 0.6643 |
| Jul | Play 3 — IB Fade | 14392 | 0.1338 | 0.009 | 0.9334 |
| Aug | Play 1 — IB Breakout | 14036 | 0.4797 | 0.1089 | 1.234 |
| Aug | Play 2 — IB Retest | 14036 | 0.0964 | 0.0324 | 0.694 |
| Aug | Play 3 — IB Fade | 14036 | 0.1256 | 0.0071 | 0.9099 |
| Sep | Play 1 — IB Breakout | 13444 | 0.4845 | 0.1044 | 1.1924 |
| Sep | Play 2 — IB Retest | 13444 | 0.1018 | 0.0461 | 0.7022 |
| Sep | Play 3 — IB Fade | 13444 | 0.1276 | 0.001 | 0.8917 |
| Oct | Play 1 — IB Breakout | 14052 | 0.4802 | 0.0967 | 1.1913 |
| Oct | Play 2 — IB Retest | 14052 | 0.0977 | 0.027 | 0.6635 |
| Oct | Play 3 — IB Fade | 14052 | 0.1326 | 0.0173 | 1.0085 |
| Nov | Play 1 — IB Breakout | 13400 | 0.5 | 0.1128 | 1.24 |
| Nov | Play 2 — IB Retest | 13400 | 0.096 | 0.0191 | 0.6401 |
| Nov | Play 3 — IB Fade | 13400 | 0.1269 | 0.0088 | 0.9547 |
| Dec | Play 1 — IB Breakout | 13200 | 0.481 | 0.0941 | 1.1534 |
| Dec | Play 2 — IB Retest | 13200 | 0.096 | 0.0044 | 0.6319 |
| Dec | Play 3 — IB Fade | 13200 | 0.1278 | -0.0011 | 0.8804 |


### ES1 — By Day of Week

| Day | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Thu | Play 1 — IB Breakout | 33680 | 0.4911 | 0.0993 | 1.1866 |
| Thu | Play 2 — IB Retest | 33680 | 0.0958 | 0.0082 | 0.6309 |
| Thu | Play 3 — IB Fade | 33680 | 0.1317 | 0.0067 | 0.9422 |
| Fri | Play 1 — IB Breakout | 32980 | 0.483 | 0.0977 | 1.1949 |
| Fri | Play 2 — IB Retest | 32980 | 0.0978 | 0.0263 | 0.6544 |
| Fri | Play 3 — IB Fade | 32980 | 0.1327 | 0.0069 | 0.9278 |
| Mon | Play 1 — IB Breakout | 31864 | 0.4547 | 0.0939 | 1.1704 |
| Mon | Play 2 — IB Retest | 31864 | 0.0869 | 0.0206 | 0.6354 |
| Mon | Play 3 — IB Fade | 31864 | 0.1181 | 0.0062 | 0.927 |
| Tue | Play 1 — IB Breakout | 33732 | 0.497 | 0.1088 | 1.2233 |
| Tue | Play 2 — IB Retest | 33732 | 0.1027 | 0.0277 | 0.6988 |
| Tue | Play 3 — IB Fade | 33732 | 0.1268 | -0.0006 | 0.8854 |
| Wed | Play 1 — IB Breakout | 33692 | 0.4948 | 0.102 | 1.2031 |
| Wed | Play 2 — IB Retest | 33692 | 0.1022 | 0.0186 | 0.6695 |
| Wed | Play 3 — IB Fade | 33692 | 0.1319 | 0.0098 | 0.9516 |


### YM1 — Overall (all sessions, all target levels)

| Play | N | Win Rate | Expectancy (R) | Profit Factor | Avg MFE | Avg MAE | Wins | Losses |
|---|---|---|---|---|---|---|---|---|
| Play 1 — IB Breakout | 150024 | 0.4661 | 0.0763 | 1.0745 | 0.0942 | 0.0869 | 69924 | 64260 |
| Play 2 — IB Retest | 150024 | 0.0921 | 0.0117 | 0.6154 | 0.0462 | 0.0352 | 13811 | 55537 |
| Play 3 — IB Fade | 150024 | 0.1251 | 0.0298 | 1.1142 | 0.0213 | 0.0192 | 18771 | 22744 |


### YM1 — By Session

| Session | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| London IB | Play 1 — IB Breakout | 37696 | 0.3659 | 0.0713 | 0.9443 |
| London IB | Play 2 — IB Retest | 37696 | 0.0253 | 0.004 | 0.2643 |
| London IB | Play 3 — IB Fade | 37696 | 0.0747 | 0.0209 | 0.9442 |
| Midnight OR | Play 1 — IB Breakout | 18836 | 0.7155 | 0.1288 | 1.4528 |
| Midnight OR | Play 2 — IB Retest | 18836 | 0.3062 | 0.0402 | 1.0648 |
| Midnight OR | Play 3 — IB Fade | 18836 | 0.2492 | 0.0601 | 1.3591 |
| NY AM IB | Play 1 — IB Breakout | 18876 | 0.4783 | 0.0621 | 0.9541 |
| NY AM IB | Play 2 — IB Retest | 18876 | 0.0723 | 0.0024 | 0.4426 |
| NY AM IB | Play 3 — IB Fade | 18876 | 0.1212 | 0.0164 | 0.9923 |
| NY PM IB | Play 1 — IB Breakout | 18260 | 0.4682 | 0.0698 | 0.9922 |
| NY PM IB | Play 2 — IB Retest | 18260 | 0.0689 | 0.0145 | 0.4491 |
| NY PM IB | Play 3 — IB Fade | 18260 | 0.1245 | 0.0339 | 1.1475 |
| Tokyo IB | Play 1 — IB Breakout | 37524 | 0.5559 | 0.0799 | 1.1423 |
| Tokyo IB | Play 2 — IB Retest | 37524 | 0.114 | 0.0159 | 0.6102 |
| Tokyo IB | Play 3 — IB Fade | 37524 | 0.1589 | 0.0338 | 1.172 |
| Globex IB | Play 1 — IB Breakout | 18832 | 0.2239 | 0.0472 | 0.7655 |
| Globex IB | Play 2 — IB Retest | 18832 | 0.0101 | -0.0033 | 0.2048 |
| Globex IB | Play 3 — IB Fade | 18832 | 0.0392 | 0.0187 | 0.8635 |


### YM1 — By Target Level (extension multiplier)

| Play | Target | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Play 1 — IB Breakout | 0.25x | 37506 | 0.7026 | 0.0698 | 1.5976 |
| Play 1 — IB Breakout | 0.5x | 37506 | 0.5101 | 0.0776 | 1.2363 |
| Play 1 — IB Breakout | 0.75x | 37506 | 0.3707 | 0.0763 | 1.0053 |
| Play 1 — IB Breakout | 1.0x | 37506 | 0.281 | 0.0815 | 0.8559 |
| Play 2 — IB Retest | 0.25x | 37506 | 0.1362 | 0.0123 | 0.7822 |
| Play 2 — IB Retest | 0.5x | 37506 | 0.0991 | 0.0112 | 0.6647 |
| Play 2 — IB Retest | 0.75x | 37506 | 0.0744 | 0.0102 | 0.5653 |
| Play 2 — IB Retest | 1.0x | 37506 | 0.0585 | 0.013 | 0.4969 |
| Play 3 — IB Fade | 0.25x | 37506 | 0.1146 | 0.0627 | 1.1712 |
| Play 3 — IB Fade | 0.5x | 37506 | 0.1369 | 0.0279 | 1.0727 |
| Play 3 — IB Fade | 0.75x | 37506 | 0.131 | 0.018 | 1.0778 |
| Play 3 — IB Fade | 1.0x | 37506 | 0.118 | 0.0106 | 1.062 |


### YM1 — By Year

| Year | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| 2008 | Play 1 — IB Breakout | 8040 | 0.5019 | 0.0665 | 1.0475 |
| 2008 | Play 2 — IB Retest | 8040 | 0.109 | 0.0251 | 0.6716 |
| 2008 | Play 3 — IB Fade | 8040 | 0.1376 | 0.0114 | 0.9837 |
| 2009 | Play 1 — IB Breakout | 8100 | 0.4635 | 0.0526 | 0.9921 |
| 2009 | Play 2 — IB Retest | 8100 | 0.1002 | 0.0148 | 0.6517 |
| 2009 | Play 3 — IB Fade | 8100 | 0.1373 | 0.0458 | 1.264 |
| 2010 | Play 1 — IB Breakout | 8216 | 0.5021 | 0.1073 | 1.2013 |
| 2010 | Play 2 — IB Retest | 8216 | 0.0937 | 0.0223 | 0.65 |
| 2010 | Play 3 — IB Fade | 8216 | 0.1259 | 0.0131 | 0.9915 |
| 2011 | Play 1 — IB Breakout | 8168 | 0.4805 | 0.0751 | 1.0653 |
| 2011 | Play 2 — IB Retest | 8168 | 0.1014 | 0.0307 | 0.6667 |
| 2011 | Play 3 — IB Fade | 8168 | 0.127 | 0.0287 | 1.0758 |
| 2012 | Play 1 — IB Breakout | 8144 | 0.4891 | 0.094 | 1.1413 |
| 2012 | Play 2 — IB Retest | 8144 | 0.0866 | 0.0038 | 0.5493 |
| 2012 | Play 3 — IB Fade | 8144 | 0.1318 | 0.0203 | 1.0521 |
| 2013 | Play 1 — IB Breakout | 8032 | 0.458 | 0.0707 | 1.0868 |
| 2013 | Play 2 — IB Retest | 8032 | 0.0843 | -0.0119 | 0.5694 |
| 2013 | Play 3 — IB Fade | 8032 | 0.1219 | 0.0293 | 1.1387 |
| 2014 | Play 1 — IB Breakout | 8008 | 0.4723 | 0.1064 | 1.2566 |
| 2014 | Play 2 — IB Retest | 8008 | 0.0827 | -0.0081 | 0.5871 |
| 2014 | Play 3 — IB Fade | 8008 | 0.1168 | 0.0144 | 0.975 |
| 2015 | Play 1 — IB Breakout | 8212 | 0.4709 | 0.0957 | 1.1979 |
| 2015 | Play 2 — IB Retest | 8212 | 0.0945 | 0.025 | 0.6672 |
| 2015 | Play 3 — IB Fade | 8212 | 0.1126 | 0.0167 | 0.9927 |
| 2016 | Play 1 — IB Breakout | 8204 | 0.4501 | 0.0769 | 1.1183 |
| 2016 | Play 2 — IB Retest | 8204 | 0.0961 | 0.0249 | 0.706 |
| 2016 | Play 3 — IB Fade | 8204 | 0.1221 | 0.0264 | 1.0509 |
| 2017 | Play 1 — IB Breakout | 8192 | 0.4413 | 0.0773 | 1.0937 |
| 2017 | Play 2 — IB Retest | 8192 | 0.0927 | 0.042 | 0.6543 |
| 2017 | Play 3 — IB Fade | 8192 | 0.13 | 0.0388 | 1.1989 |
| 2018 | Play 1 — IB Breakout | 8212 | 0.4861 | 0.0841 | 1.1249 |
| 2018 | Play 2 — IB Retest | 8212 | 0.0934 | 0.006 | 0.6145 |
| 2018 | Play 3 — IB Fade | 8212 | 0.1302 | 0.0414 | 1.2048 |
| 2019 | Play 1 — IB Breakout | 8216 | 0.4589 | 0.0716 | 1.0249 |
| 2019 | Play 2 — IB Retest | 8216 | 0.0852 | -0.0086 | 0.5559 |
| 2019 | Play 3 — IB Fade | 8216 | 0.1246 | 0.0342 | 1.1154 |
| 2020 | Play 1 — IB Breakout | 8232 | 0.4855 | 0.1034 | 1.189 |
| 2020 | Play 2 — IB Retest | 8232 | 0.1003 | 0.0432 | 0.7125 |
| 2020 | Play 3 — IB Fade | 8232 | 0.1212 | 0.0457 | 1.3427 |
| 2021 | Play 1 — IB Breakout | 8248 | 0.4407 | 0.0628 | 0.9809 |
| 2021 | Play 2 — IB Retest | 8248 | 0.0833 | 0.0075 | 0.5633 |
| 2021 | Play 3 — IB Fade | 8248 | 0.1202 | 0.032 | 1.0993 |
| 2022 | Play 1 — IB Breakout | 8204 | 0.4562 | 0.0541 | 0.9448 |
| 2022 | Play 2 — IB Retest | 8204 | 0.0854 | -0.0279 | 0.5369 |
| 2022 | Play 3 — IB Fade | 8204 | 0.1312 | 0.036 | 1.1958 |
| 2023 | Play 1 — IB Breakout | 7996 | 0.4614 | 0.0769 | 1.0647 |
| 2023 | Play 2 — IB Retest | 7996 | 0.0964 | 0.0288 | 0.6123 |
| 2023 | Play 3 — IB Fade | 7996 | 0.1312 | 0.0409 | 1.2131 |
| 2024 | Play 1 — IB Breakout | 8248 | 0.4327 | 0.0351 | 0.9078 |
| 2024 | Play 2 — IB Retest | 8248 | 0.0829 | -0.0211 | 0.5134 |
| 2024 | Play 3 — IB Fade | 8248 | 0.1237 | 0.0388 | 1.236 |
| 2025 | Play 1 — IB Breakout | 7680 | 0.4418 | 0.0626 | 0.9935 |
| 2025 | Play 2 — IB Retest | 7680 | 0.0924 | 0.0196 | 0.6316 |
| 2025 | Play 3 — IB Fade | 7680 | 0.1173 | 0.0318 | 1.1219 |
| 2026 | Play 1 — IB Breakout | 3672 | 0.457 | 0.0759 | 1.0624 |
| 2026 | Play 2 — IB Retest | 3672 | 0.085 | -0.0003 | 0.5883 |
| 2026 | Play 3 — IB Fade | 3672 | 0.1021 | 0.0079 | 0.9215 |


### YM1 — By Month (aggregated across all years)

| Month | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Jan | Play 1 — IB Breakout | 11848 | 0.4836 | 0.0951 | 1.1777 |
| Jan | Play 2 — IB Retest | 11848 | 0.094 | 0.0106 | 0.6594 |
| Jan | Play 3 — IB Fade | 11848 | 0.1261 | 0.0184 | 1.0357 |
| Feb | Play 1 — IB Breakout | 12096 | 0.4704 | 0.0679 | 1.0555 |
| Feb | Play 2 — IB Retest | 12096 | 0.0857 | -0.0117 | 0.553 |
| Feb | Play 3 — IB Fade | 12096 | 0.1297 | 0.0352 | 1.1649 |
| Mar | Play 1 — IB Breakout | 13144 | 0.4788 | 0.0819 | 1.1113 |
| Mar | Play 2 — IB Retest | 13144 | 0.1002 | 0.0178 | 0.6715 |
| Mar | Play 3 — IB Fade | 13144 | 0.1267 | 0.0279 | 1.1171 |
| Apr | Play 1 — IB Breakout | 12384 | 0.4642 | 0.074 | 1.0773 |
| Apr | Play 2 — IB Retest | 12384 | 0.0941 | 0.0203 | 0.6065 |
| Apr | Play 3 — IB Fade | 12384 | 0.1286 | 0.0331 | 1.1436 |
| May | Play 1 — IB Breakout | 13260 | 0.4577 | 0.0681 | 1.0232 |
| May | Play 2 — IB Retest | 13260 | 0.0938 | 0.0167 | 0.6141 |
| May | Play 3 — IB Fade | 13260 | 0.1223 | 0.0341 | 1.1468 |
| Jun | Play 1 — IB Breakout | 12936 | 0.4633 | 0.0793 | 1.0953 |
| Jun | Play 2 — IB Retest | 12936 | 0.0957 | 0.0301 | 0.6525 |
| Jun | Play 3 — IB Fade | 12936 | 0.1273 | 0.033 | 1.1376 |
| Jul | Play 1 — IB Breakout | 13084 | 0.4531 | 0.0658 | 1.013 |
| Jul | Play 2 — IB Retest | 13084 | 0.0822 | -0.0165 | 0.5493 |
| Jul | Play 3 — IB Fade | 13084 | 0.1235 | 0.021 | 1.0489 |
| Aug | Play 1 — IB Breakout | 12676 | 0.4542 | 0.0751 | 1.0658 |
| Aug | Play 2 — IB Retest | 12676 | 0.0957 | 0.0305 | 0.6644 |
| Aug | Play 3 — IB Fade | 12676 | 0.1151 | 0.0314 | 1.1046 |
| Sep | Play 1 — IB Breakout | 12264 | 0.4645 | 0.0852 | 1.0958 |
| Sep | Play 2 — IB Retest | 12264 | 0.093 | 0.0286 | 0.6386 |
| Sep | Play 3 — IB Fade | 12264 | 0.1202 | 0.0347 | 1.1475 |
| Oct | Play 1 — IB Breakout | 12700 | 0.461 | 0.066 | 1.0367 |
| Oct | Play 2 — IB Retest | 12700 | 0.0866 | -0.0084 | 0.5553 |
| Oct | Play 3 — IB Fade | 12700 | 0.1289 | 0.0301 | 1.1161 |
| Nov | Play 1 — IB Breakout | 12092 | 0.4826 | 0.0897 | 1.1161 |
| Nov | Play 2 — IB Retest | 12092 | 0.0896 | 0.0065 | 0.589 |
| Nov | Play 3 — IB Fade | 12092 | 0.1273 | 0.028 | 1.1063 |
| Dec | Play 1 — IB Breakout | 11540 | 0.4616 | 0.0692 | 1.0441 |
| Dec | Play 2 — IB Retest | 11540 | 0.0938 | 0.0157 | 0.6419 |
| Dec | Play 3 — IB Fade | 11540 | 0.1261 | 0.0304 | 1.1111 |


### YM1 — By Day of Week

| Day | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Wed | Play 1 — IB Breakout | 30252 | 0.469 | 0.0659 | 1.0466 |
| Wed | Play 2 — IB Retest | 30252 | 0.0948 | 0.0029 | 0.6074 |
| Wed | Play 3 — IB Fade | 30252 | 0.1275 | 0.0349 | 1.1504 |
| Thu | Play 1 — IB Breakout | 30260 | 0.4749 | 0.0782 | 1.0766 |
| Thu | Play 2 — IB Retest | 30260 | 0.0921 | 0.0017 | 0.5976 |
| Thu | Play 3 — IB Fade | 30260 | 0.1285 | 0.0319 | 1.1419 |
| Fri | Play 1 — IB Breakout | 29508 | 0.4621 | 0.0681 | 1.0334 |
| Fri | Play 2 — IB Retest | 29508 | 0.0874 | 0.0022 | 0.5576 |
| Fri | Play 3 — IB Fade | 29508 | 0.1282 | 0.0294 | 1.1184 |
| Mon | Play 1 — IB Breakout | 29684 | 0.4375 | 0.075 | 1.0678 |
| Mon | Play 2 — IB Retest | 29684 | 0.0869 | 0.0245 | 0.6452 |
| Mon | Play 3 — IB Fade | 29684 | 0.1166 | 0.0288 | 1.1133 |
| Tue | Play 1 — IB Breakout | 30320 | 0.4862 | 0.0939 | 1.1501 |
| Tue | Play 2 — IB Retest | 30320 | 0.0988 | 0.0271 | 0.6746 |
| Tue | Play 3 — IB Fade | 30320 | 0.1247 | 0.024 | 1.0492 |


### RTY1 — Overall (all sessions, all target levels)

| Play | N | Win Rate | Expectancy (R) | Profit Factor | Avg MFE | Avg MAE | Wins | Losses |
|---|---|---|---|---|---|---|---|---|
| Play 1 — IB Breakout | 72552 | 0.4576 | 0.0743 | 1.0388 | 0.1344 | 0.1244 | 33201 | 32151 |
| Play 2 — IB Retest | 72552 | 0.083 | 0.0061 | 0.5875 | 0.0604 | 0.046 | 6022 | 25902 |
| Play 3 — IB Fade | 72552 | 0.1173 | 0.0269 | 1.0797 | 0.0291 | 0.0258 | 8507 | 10832 |


### RTY1 — By Session

| Session | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Globex IB | Play 1 — IB Breakout | 9116 | 0.2274 | 0.0621 | 0.7994 |
| Globex IB | Play 2 — IB Retest | 9116 | 0.0087 | 0.0066 | 0.2211 |
| Globex IB | Play 3 — IB Fade | 9116 | 0.0302 | 0.0115 | 0.7207 |
| NY AM IB | Play 1 — IB Breakout | 9112 | 0.4241 | 0.0615 | 0.8875 |
| NY AM IB | Play 2 — IB Retest | 9112 | 0.0498 | 0.0147 | 0.3568 |
| NY AM IB | Play 3 — IB Fade | 9112 | 0.0978 | 0.0036 | 0.8759 |
| NY PM IB | Play 1 — IB Breakout | 8804 | 0.438 | 0.0477 | 0.8883 |
| NY PM IB | Play 2 — IB Retest | 8804 | 0.058 | 0.0069 | 0.3802 |
| NY PM IB | Play 3 — IB Fade | 8804 | 0.1222 | 0.04 | 1.2065 |
| Tokyo IB | Play 1 — IB Breakout | 18272 | 0.5263 | 0.0662 | 1.0483 |
| Tokyo IB | Play 2 — IB Retest | 18272 | 0.0894 | -0.0158 | 0.5085 |
| Tokyo IB | Play 3 — IB Fade | 18272 | 0.1444 | 0.0263 | 1.1035 |
| London IB | Play 1 — IB Breakout | 18188 | 0.3977 | 0.0765 | 0.9754 |
| London IB | Play 2 — IB Retest | 18188 | 0.0361 | 0.0059 | 0.3833 |
| London IB | Play 3 — IB Fade | 18188 | 0.0804 | 0.0253 | 0.9727 |
| Midnight OR | Play 1 — IB Breakout | 9060 | 0.7237 | 0.1371 | 1.4955 |
| Midnight OR | Play 2 — IB Retest | 9060 | 0.2968 | 0.0408 | 1.0671 |
| Midnight OR | Play 3 — IB Fade | 9060 | 0.2389 | 0.0573 | 1.3669 |


### RTY1 — By Target Level (extension multiplier)

| Play | Target | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Play 1 — IB Breakout | 0.25x | 18138 | 0.6998 | 0.0697 | 1.5938 |
| Play 1 — IB Breakout | 0.5x | 18138 | 0.5034 | 0.0755 | 1.2169 |
| Play 1 — IB Breakout | 0.75x | 18138 | 0.3621 | 0.0738 | 0.9768 |
| Play 1 — IB Breakout | 1.0x | 18138 | 0.2652 | 0.0782 | 0.7961 |
| Play 2 — IB Retest | 0.25x | 18138 | 0.1229 | 0.0035 | 0.7447 |
| Play 2 — IB Retest | 0.5x | 18138 | 0.0896 | 0.0061 | 0.6359 |
| Play 2 — IB Retest | 0.75x | 18138 | 0.0663 | 0.0044 | 0.5324 |
| Play 2 — IB Retest | 1.0x | 18138 | 0.0531 | 0.0104 | 0.4807 |
| Play 3 — IB Fade | 0.25x | 18138 | 0.1097 | 0.0566 | 1.1338 |
| Play 3 — IB Fade | 0.5x | 18138 | 0.1312 | 0.0252 | 1.0351 |
| Play 3 — IB Fade | 0.75x | 18138 | 0.1212 | 0.0141 | 1.0237 |
| Play 3 — IB Fade | 1.0x | 18138 | 0.1068 | 0.0116 | 1.0718 |


### RTY1 — By Year

| Year | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| 2017 | Play 1 — IB Breakout | 3860 | 0.4917 | 0.0919 | 1.136 |
| 2017 | Play 2 — IB Retest | 3860 | 0.0609 | -0.0123 | 0.5205 |
| 2017 | Play 3 — IB Fade | 3860 | 0.1044 | 0.0308 | 1.1597 |
| 2018 | Play 1 — IB Breakout | 8208 | 0.4854 | 0.0887 | 1.1222 |
| 2018 | Play 2 — IB Retest | 8208 | 0.0936 | 0.0288 | 0.7 |
| 2018 | Play 3 — IB Fade | 8208 | 0.1162 | 0.0239 | 1.0391 |
| 2019 | Play 1 — IB Breakout | 8216 | 0.4546 | 0.0768 | 1.0355 |
| 2019 | Play 2 — IB Retest | 8216 | 0.0721 | -0.0328 | 0.4864 |
| 2019 | Play 3 — IB Fade | 8216 | 0.1167 | 0.0273 | 1.0938 |
| 2020 | Play 1 — IB Breakout | 8236 | 0.4703 | 0.0928 | 1.1401 |
| 2020 | Play 2 — IB Retest | 8236 | 0.0901 | 0.031 | 0.6476 |
| 2020 | Play 3 — IB Fade | 8236 | 0.1181 | 0.024 | 1.0981 |
| 2021 | Play 1 — IB Breakout | 8248 | 0.4253 | 0.0472 | 0.9171 |
| 2021 | Play 2 — IB Retest | 8248 | 0.0717 | -0.019 | 0.5066 |
| 2021 | Play 3 — IB Fade | 8248 | 0.1138 | 0.0302 | 1.0938 |
| 2022 | Play 1 — IB Breakout | 8204 | 0.4427 | 0.0446 | 0.8882 |
| 2022 | Play 2 — IB Retest | 8204 | 0.0733 | -0.0427 | 0.465 |
| 2022 | Play 3 — IB Fade | 8204 | 0.1186 | 0.0291 | 1.1049 |
| 2023 | Play 1 — IB Breakout | 7996 | 0.4586 | 0.0895 | 1.1061 |
| 2023 | Play 2 — IB Retest | 7996 | 0.0914 | 0.0409 | 0.6644 |
| 2023 | Play 3 — IB Fade | 7996 | 0.1173 | 0.0215 | 1.0157 |
| 2024 | Play 1 — IB Breakout | 8248 | 0.4573 | 0.0756 | 1.0643 |
| 2024 | Play 2 — IB Retest | 8248 | 0.0911 | 0.0135 | 0.6277 |
| 2024 | Play 3 — IB Fade | 8248 | 0.1212 | 0.0353 | 1.158 |
| 2025 | Play 1 — IB Breakout | 7664 | 0.4495 | 0.0749 | 1.0261 |
| 2025 | Play 2 — IB Retest | 7664 | 0.0922 | 0.0366 | 0.6556 |
| 2025 | Play 3 — IB Fade | 7664 | 0.1211 | 0.0281 | 1.0791 |
| 2026 | Play 1 — IB Breakout | 3672 | 0.4594 | 0.0664 | 1.0376 |
| 2026 | Play 2 — IB Retest | 3672 | 0.0828 | 0.0154 | 0.5925 |
| 2026 | Play 3 — IB Fade | 3672 | 0.1198 | 0.0128 | 0.939 |


### RTY1 — By Month (aggregated across all years)

| Month | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Jul | Play 1 — IB Breakout | 6636 | 0.4572 | 0.0859 | 1.0621 |
| Jul | Play 2 — IB Retest | 6636 | 0.0781 | -0.0012 | 0.5652 |
| Jul | Play 3 — IB Fade | 6636 | 0.1133 | 0.0165 | 0.9777 |
| Aug | Play 1 — IB Breakout | 6384 | 0.4508 | 0.0721 | 1.0269 |
| Aug | Play 2 — IB Retest | 6384 | 0.0727 | -0.0071 | 0.5167 |
| Aug | Play 3 — IB Fade | 6384 | 0.1129 | 0.031 | 1.15 |
| Sep | Play 1 — IB Breakout | 6088 | 0.4405 | 0.0685 | 0.982 |
| Sep | Play 2 — IB Retest | 6088 | 0.0807 | 0.0194 | 0.5756 |
| Sep | Play 3 — IB Fade | 6088 | 0.1114 | 0.022 | 1.0391 |
| Oct | Play 1 — IB Breakout | 6388 | 0.4637 | 0.0802 | 1.0812 |
| Oct | Play 2 — IB Retest | 6388 | 0.0803 | -0.0039 | 0.5749 |
| Oct | Play 3 — IB Fade | 6388 | 0.1144 | 0.0271 | 1.0631 |
| Nov | Play 1 — IB Breakout | 6072 | 0.4732 | 0.0755 | 1.0272 |
| Nov | Play 2 — IB Retest | 6072 | 0.0838 | -0.015 | 0.5487 |
| Nov | Play 3 — IB Fade | 6072 | 0.1219 | 0.0296 | 1.1232 |
| Dec | Play 1 — IB Breakout | 5528 | 0.4501 | 0.0467 | 0.9371 |
| Dec | Play 2 — IB Retest | 5528 | 0.0874 | -0.0127 | 0.5913 |
| Dec | Play 3 — IB Fade | 5528 | 0.1275 | 0.0361 | 1.1646 |
| Jan | Play 1 — IB Breakout | 5464 | 0.4791 | 0.1182 | 1.2404 |
| Jan | Play 2 — IB Retest | 5464 | 0.1018 | 0.0752 | 0.7872 |
| Jan | Play 3 — IB Fade | 5464 | 0.1129 | 0.0234 | 1.0591 |
| Feb | Play 1 — IB Breakout | 5616 | 0.4494 | 0.0612 | 1.0126 |
| Feb | Play 2 — IB Retest | 5616 | 0.0853 | 0.0165 | 0.5788 |
| Feb | Play 3 — IB Fade | 5616 | 0.1181 | 0.0395 | 1.1928 |
| Mar | Play 1 — IB Breakout | 6196 | 0.4784 | 0.09 | 1.1178 |
| Mar | Play 2 — IB Retest | 6196 | 0.0881 | 0.004 | 0.6273 |
| Mar | Play 3 — IB Fade | 6196 | 0.1135 | 0.0148 | 0.9806 |
| Apr | Play 1 — IB Breakout | 5812 | 0.4491 | 0.055 | 0.9937 |
| Apr | Play 2 — IB Retest | 5812 | 0.0893 | 0.0116 | 0.6217 |
| Apr | Play 3 — IB Fade | 5812 | 0.1177 | 0.0259 | 1.0374 |
| May | Play 1 — IB Breakout | 6260 | 0.453 | 0.0867 | 1.0847 |
| May | Play 2 — IB Retest | 6260 | 0.0826 | 0.0296 | 0.6195 |
| May | Play 3 — IB Fade | 6260 | 0.1195 | 0.0197 | 1.0408 |
| Jun | Play 1 — IB Breakout | 6108 | 0.4473 | 0.0497 | 0.945 |
| Jun | Play 2 — IB Retest | 6108 | 0.0699 | -0.0353 | 0.4855 |
| Jun | Play 3 — IB Fade | 6108 | 0.1252 | 0.0393 | 1.1769 |


### RTY1 — By Day of Week

| Day | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Mon | Play 1 — IB Breakout | 14324 | 0.4247 | 0.071 | 1.0216 |
| Mon | Play 2 — IB Retest | 14324 | 0.0725 | 0.0069 | 0.5515 |
| Mon | Play 3 — IB Fade | 14324 | 0.1077 | 0.0243 | 1.0486 |
| Tue | Play 1 — IB Breakout | 14664 | 0.4699 | 0.0801 | 1.0551 |
| Tue | Play 2 — IB Retest | 14664 | 0.0834 | 0.0026 | 0.5992 |
| Tue | Play 3 — IB Fade | 14664 | 0.1177 | 0.0246 | 1.0757 |
| Wed | Play 1 — IB Breakout | 14576 | 0.4652 | 0.0675 | 1.0164 |
| Wed | Play 2 — IB Retest | 14576 | 0.0922 | 0.0153 | 0.6136 |
| Wed | Play 3 — IB Fade | 14576 | 0.1238 | 0.0331 | 1.1451 |
| Thu | Play 1 — IB Breakout | 14640 | 0.4602 | 0.0647 | 0.9981 |
| Thu | Play 2 — IB Retest | 14640 | 0.0805 | -0.0132 | 0.5546 |
| Thu | Play 3 — IB Fade | 14640 | 0.12 | 0.0288 | 1.1043 |
| Fri | Play 1 — IB Breakout | 14348 | 0.4677 | 0.0884 | 1.108 |
| Fri | Play 2 — IB Retest | 14348 | 0.0863 | 0.0192 | 0.6154 |
| Fri | Play 3 — IB Fade | 14348 | 0.1169 | 0.0234 | 1.0246 |


### CL1 — Overall (all sessions, all target levels)

| Play | N | Win Rate | Expectancy (R) | Profit Factor | Avg MFE | Avg MAE | Wins | Losses |
|---|---|---|---|---|---|---|---|---|
| Play 1 — IB Breakout | 146496 | 0.4726 | 0.0999 | 1.2484 | 0.4113 | 0.3623 | 69230 | 55854 |
| Play 2 — IB Retest | 146496 | 0.0956 | 0.0012 | 0.6583 | 0.1968 | 0.1516 | 14012 | 51340 |
| Play 3 — IB Fade | 146496 | 0.1207 | 0.022 | 1.063 | 0.089 | 0.0855 | 17689 | 21351 |


### CL1 — By Session

| Session | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Globex IB | Play 1 — IB Breakout | 18372 | 0.1782 | 0.0542 | 0.8361 |
| Globex IB | Play 2 — IB Retest | 18372 | 0.0034 | -0.003 | 0.1117 |
| Globex IB | Play 3 — IB Fade | 18372 | 0.0225 | 0.0014 | 0.5264 |
| London IB | Play 1 — IB Breakout | 36728 | 0.4834 | 0.0928 | 1.126 |
| London IB | Play 2 — IB Retest | 36728 | 0.0559 | -0.0102 | 0.4089 |
| London IB | Play 3 — IB Fade | 36728 | 0.1112 | 0.0281 | 1.0788 |
| Midnight OR | Play 1 — IB Breakout | 18336 | 0.7387 | 0.1671 | 1.6398 |
| Midnight OR | Play 2 — IB Retest | 18336 | 0.2967 | -0.0092 | 0.9848 |
| Midnight OR | Play 3 — IB Fade | 18336 | 0.2366 | 0.0404 | 1.2369 |
| NY AM IB | Play 1 — IB Breakout | 18364 | 0.5713 | 0.123 | 1.3047 |
| NY AM IB | Play 2 — IB Retest | 18364 | 0.1053 | 0.0292 | 0.614 |
| NY AM IB | Play 3 — IB Fade | 18364 | 0.1498 | 0.0334 | 1.1672 |
| NY PM IB | Play 1 — IB Breakout | 17980 | 0.1172 | 0.0343 | 0.5388 |
| NY PM IB | Play 2 — IB Retest | 17980 | 0.0019 | 0.0009 | 0.1233 |
| NY PM IB | Play 3 — IB Fade | 17980 | 0.0109 | -0.0005 | 0.3732 |
| Tokyo IB | Play 1 — IB Breakout | 36716 | 0.6008 | 0.117 | 1.3306 |
| Tokyo IB | Play 2 — IB Retest | 36716 | 0.1223 | 0.0062 | 0.6425 |
| Tokyo IB | Play 3 — IB Fade | 36716 | 0.1609 | 0.0222 | 1.0846 |


### CL1 — By Target Level (extension multiplier)

| Play | Target | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Play 1 — IB Breakout | 0.25x | 36624 | 0.6879 | 0.0868 | 1.9279 |
| Play 1 — IB Breakout | 0.5x | 36624 | 0.5123 | 0.0999 | 1.4148 |
| Play 1 — IB Breakout | 0.75x | 36624 | 0.3877 | 0.1031 | 1.1703 |
| Play 1 — IB Breakout | 1.0x | 36624 | 0.3023 | 0.1099 | 1.0101 |
| Play 2 — IB Retest | 0.25x | 36624 | 0.1394 | 0.005 | 0.8189 |
| Play 2 — IB Retest | 0.5x | 36624 | 0.1029 | 0.0024 | 0.7065 |
| Play 2 — IB Retest | 0.75x | 36624 | 0.0786 | -0.0008 | 0.6144 |
| Play 2 — IB Retest | 1.0x | 36624 | 0.0617 | -0.0016 | 0.539 |
| Play 3 — IB Fade | 0.25x | 36624 | 0.1018 | 0.0445 | 1.0863 |
| Play 3 — IB Fade | 0.5x | 36624 | 0.1301 | 0.0219 | 1.0502 |
| Play 3 — IB Fade | 0.75x | 36624 | 0.1298 | 0.013 | 1.0403 |
| Play 3 — IB Fade | 1.0x | 36624 | 0.1213 | 0.0085 | 1.0475 |


### CL1 — By Year

| Year | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| 2008 | Play 1 — IB Breakout | 3680 | 0.4913 | 0.119 | 1.3396 |
| 2008 | Play 2 — IB Retest | 3680 | 0.0886 | -0.0124 | 0.6181 |
| 2008 | Play 3 — IB Fade | 3680 | 0.1179 | 0.0248 | 1.1399 |
| 2009 | Play 1 — IB Breakout | 8184 | 0.4596 | 0.0888 | 1.2245 |
| 2009 | Play 2 — IB Retest | 8184 | 0.0882 | 0.0016 | 0.606 |
| 2009 | Play 3 — IB Fade | 8184 | 0.1173 | 0.03 | 1.1257 |
| 2010 | Play 1 — IB Breakout | 8196 | 0.4608 | 0.0988 | 1.1984 |
| 2010 | Play 2 — IB Retest | 8196 | 0.0931 | -0.0079 | 0.6438 |
| 2010 | Play 3 — IB Fade | 8196 | 0.1092 | 0.0135 | 1.0218 |
| 2011 | Play 1 — IB Breakout | 8228 | 0.4646 | 0.0786 | 1.1369 |
| 2011 | Play 2 — IB Retest | 8228 | 0.0997 | -0.0106 | 0.6643 |
| 2011 | Play 3 — IB Fade | 8228 | 0.1208 | 0.0165 | 1.0108 |
| 2012 | Play 1 — IB Breakout | 8220 | 0.4773 | 0.121 | 1.352 |
| 2012 | Play 2 — IB Retest | 8220 | 0.1086 | 0.0592 | 0.7778 |
| 2012 | Play 3 — IB Fade | 8220 | 0.1248 | 0.0182 | 1.0292 |
| 2013 | Play 1 — IB Breakout | 8124 | 0.4557 | 0.0843 | 1.1991 |
| 2013 | Play 2 — IB Retest | 8124 | 0.0986 | -0.0085 | 0.6698 |
| 2013 | Play 3 — IB Fade | 8124 | 0.1259 | 0.0272 | 1.1152 |
| 2014 | Play 1 — IB Breakout | 8064 | 0.4826 | 0.1041 | 1.2921 |
| 2014 | Play 2 — IB Retest | 8064 | 0.088 | -0.0271 | 0.6043 |
| 2014 | Play 3 — IB Fade | 8064 | 0.1221 | 0.0258 | 1.1391 |
| 2015 | Play 1 — IB Breakout | 8216 | 0.4652 | 0.1193 | 1.4241 |
| 2015 | Play 2 — IB Retest | 8216 | 0.0892 | 0.003 | 0.6509 |
| 2015 | Play 3 — IB Fade | 8216 | 0.1151 | 0.0144 | 1.0159 |
| 2016 | Play 1 — IB Breakout | 8232 | 0.4628 | 0.1133 | 1.3239 |
| 2016 | Play 2 — IB Retest | 8232 | 0.0747 | -0.0299 | 0.5673 |
| 2016 | Play 3 — IB Fade | 8232 | 0.1052 | 0.0086 | 0.9541 |
| 2017 | Play 1 — IB Breakout | 8200 | 0.4649 | 0.1136 | 1.3846 |
| 2017 | Play 2 — IB Retest | 8200 | 0.0972 | 0.0341 | 0.7318 |
| 2017 | Play 3 — IB Fade | 8200 | 0.1132 | 0.001 | 0.8658 |
| 2018 | Play 1 — IB Breakout | 8228 | 0.501 | 0.1283 | 1.4314 |
| 2018 | Play 2 — IB Retest | 8228 | 0.0895 | -0.0133 | 0.6325 |
| 2018 | Play 3 — IB Fade | 8228 | 0.1207 | 0.0233 | 1.0602 |
| 2019 | Play 1 — IB Breakout | 8228 | 0.4646 | 0.0727 | 1.124 |
| 2019 | Play 2 — IB Retest | 8228 | 0.1048 | -0.0022 | 0.6606 |
| 2019 | Play 3 — IB Fade | 8228 | 0.1392 | 0.0311 | 1.115 |
| 2020 | Play 1 — IB Breakout | 8256 | 0.4516 | 0.0874 | 1.1884 |
| 2020 | Play 2 — IB Retest | 8256 | 0.0947 | 0.0468 | 0.6758 |
| 2020 | Play 3 — IB Fade | 8256 | 0.1204 | 0.0254 | 1.0603 |
| 2021 | Play 1 — IB Breakout | 8228 | 0.4939 | 0.1161 | 1.2658 |
| 2021 | Play 2 — IB Retest | 8228 | 0.0915 | -0.0211 | 0.6289 |
| 2021 | Play 3 — IB Fade | 8228 | 0.1161 | 0.0125 | 0.9818 |
| 2022 | Play 1 — IB Breakout | 8212 | 0.4766 | 0.0832 | 1.171 |
| 2022 | Play 2 — IB Retest | 8212 | 0.1008 | 0.0155 | 0.6738 |
| 2022 | Play 3 — IB Fade | 8212 | 0.128 | 0.0419 | 1.2179 |
| 2023 | Play 1 — IB Breakout | 8204 | 0.4923 | 0.1193 | 1.3305 |
| 2023 | Play 2 — IB Retest | 8204 | 0.1059 | 0.0026 | 0.6872 |
| 2023 | Play 3 — IB Fade | 8204 | 0.1209 | 0.0208 | 1.0583 |
| 2024 | Play 1 — IB Breakout | 8276 | 0.4874 | 0.0969 | 1.1957 |
| 2024 | Play 2 — IB Retest | 8276 | 0.112 | 0.0189 | 0.7086 |
| 2024 | Play 3 — IB Fade | 8276 | 0.1266 | 0.0215 | 1.075 |
| 2025 | Play 1 — IB Breakout | 8004 | 0.4668 | 0.0786 | 1.105 |
| 2025 | Play 2 — IB Retest | 8004 | 0.0988 | -0.0104 | 0.6665 |
| 2025 | Play 3 — IB Fade | 8004 | 0.1294 | 0.0363 | 1.1936 |
| 2026 | Play 1 — IB Breakout | 3516 | 0.4664 | 0.0648 | 1.1223 |
| 2026 | Play 2 — IB Retest | 3516 | 0.0808 | -0.0565 | 0.5514 |
| 2026 | Play 3 — IB Fade | 3516 | 0.1189 | 0.0326 | 1.217 |


### CL1 — By Month (aggregated across all years)

| Month | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Jul | Play 1 — IB Breakout | 12600 | 0.4682 | 0.0847 | 1.1768 |
| Jul | Play 2 — IB Retest | 12600 | 0.0965 | -0.0157 | 0.6452 |
| Jul | Play 3 — IB Fade | 12600 | 0.1292 | 0.0249 | 1.1141 |
| Aug | Play 1 — IB Breakout | 12680 | 0.4677 | 0.1042 | 1.2737 |
| Aug | Play 2 — IB Retest | 12680 | 0.1042 | 0.0274 | 0.7152 |
| Aug | Play 3 — IB Fade | 12680 | 0.123 | 0.0246 | 1.0976 |
| Sep | Play 1 — IB Breakout | 12292 | 0.4694 | 0.085 | 1.196 |
| Sep | Play 2 — IB Retest | 12292 | 0.0902 | -0.0214 | 0.6334 |
| Sep | Play 3 — IB Fade | 12292 | 0.1191 | 0.0243 | 1.0714 |
| Oct | Play 1 — IB Breakout | 12756 | 0.4682 | 0.0999 | 1.2688 |
| Oct | Play 2 — IB Retest | 12756 | 0.0978 | 0.0126 | 0.6598 |
| Oct | Play 3 — IB Fade | 12756 | 0.1177 | 0.0193 | 1.0187 |
| Nov | Play 1 — IB Breakout | 12176 | 0.4765 | 0.1046 | 1.2462 |
| Nov | Play 2 — IB Retest | 12176 | 0.0968 | -0.0006 | 0.6657 |
| Nov | Play 3 — IB Fade | 12176 | 0.1189 | 0.0197 | 1.0451 |
| Dec | Play 1 — IB Breakout | 11944 | 0.4769 | 0.1164 | 1.3429 |
| Dec | Play 2 — IB Retest | 11944 | 0.0961 | 0.018 | 0.6887 |
| Dec | Play 3 — IB Fade | 11944 | 0.1181 | 0.0252 | 1.0711 |
| Jan | Play 1 — IB Breakout | 11332 | 0.4884 | 0.1125 | 1.2899 |
| Jan | Play 2 — IB Retest | 11332 | 0.1043 | 0.0254 | 0.7444 |
| Jan | Play 3 — IB Fade | 11332 | 0.1245 | 0.0222 | 1.0697 |
| Feb | Play 1 — IB Breakout | 11456 | 0.4689 | 0.1004 | 1.2251 |
| Feb | Play 2 — IB Retest | 11456 | 0.0907 | -0.0066 | 0.6399 |
| Feb | Play 3 — IB Fade | 11456 | 0.1248 | 0.0211 | 1.0736 |
| Mar | Play 1 — IB Breakout | 12532 | 0.4698 | 0.1044 | 1.2653 |
| Mar | Play 2 — IB Retest | 12532 | 0.0972 | 0.0045 | 0.6573 |
| Mar | Play 3 — IB Fade | 12532 | 0.1179 | 0.0159 | 1.014 |
| Apr | Play 1 — IB Breakout | 11896 | 0.4671 | 0.0863 | 1.2217 |
| Apr | Play 2 — IB Retest | 11896 | 0.0836 | -0.0315 | 0.5583 |
| Apr | Play 3 — IB Fade | 11896 | 0.1179 | 0.0275 | 1.1383 |
| May | Play 1 — IB Breakout | 12572 | 0.4773 | 0.0997 | 1.241 |
| May | Play 2 — IB Retest | 12572 | 0.0949 | -0.0074 | 0.6644 |
| May | Play 3 — IB Fade | 12572 | 0.1165 | 0.0112 | 0.9551 |
| Jun | Play 1 — IB Breakout | 12260 | 0.4737 | 0.1021 | 1.25 |
| Jun | Play 2 — IB Retest | 12260 | 0.0949 | 0.0103 | 0.6335 |
| Jun | Play 3 — IB Fade | 12260 | 0.1218 | 0.0282 | 1.1125 |


### CL1 — By Day of Week

| Day | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Mon | Play 1 — IB Breakout | 29016 | 0.457 | 0.1044 | 1.2768 |
| Mon | Play 2 — IB Retest | 29016 | 0.0889 | 0.0098 | 0.6693 |
| Mon | Play 3 — IB Fade | 29016 | 0.11 | 0.0168 | 1.0196 |
| Tue | Play 1 — IB Breakout | 29624 | 0.4771 | 0.1081 | 1.29 |
| Tue | Play 2 — IB Retest | 29624 | 0.1008 | 0.0252 | 0.7019 |
| Tue | Play 3 — IB Fade | 29624 | 0.1202 | 0.0225 | 1.0554 |
| Wed | Play 1 — IB Breakout | 29528 | 0.4839 | 0.096 | 1.2426 |
| Wed | Play 2 — IB Retest | 29528 | 0.101 | -0.0123 | 0.6453 |
| Wed | Play 3 — IB Fade | 29528 | 0.1307 | 0.0263 | 1.1112 |
| Thu | Play 1 — IB Breakout | 29544 | 0.4766 | 0.0994 | 1.2415 |
| Thu | Play 2 — IB Retest | 29544 | 0.0968 | -0.0029 | 0.6693 |
| Thu | Play 3 — IB Fade | 29544 | 0.1214 | 0.0244 | 1.0928 |
| Fri | Play 1 — IB Breakout | 28784 | 0.4678 | 0.0915 | 1.1945 |
| Fri | Play 2 — IB Retest | 28784 | 0.0905 | -0.0139 | 0.6081 |
| Fri | Play 3 — IB Fade | 28784 | 0.1212 | 0.0198 | 1.0345 |


### GC1 — Overall (all sessions, all target levels)

| Play | N | Win Rate | Expectancy (R) | Profit Factor | Avg MFE | Avg MAE | Wins | Losses |
|---|---|---|---|---|---|---|---|---|
| Play 1 — IB Breakout | 148896 | 0.476 | 0.1024 | 1.2376 | 0.0854 | 0.0698 | 70879 | 59917 |
| Play 2 — IB Retest | 148896 | 0.0892 | 0.0129 | 0.6327 | 0.0384 | 0.0282 | 13288 | 52964 |
| Play 3 — IB Fade | 148896 | 0.1201 | 0.0247 | 1.0523 | 0.0181 | 0.0169 | 17881 | 22851 |


### GC1 — By Session

| Session | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Globex IB | Play 1 — IB Breakout | 18672 | 0.2792 | 0.0632 | 0.8945 |
| Globex IB | Play 2 — IB Retest | 18672 | 0.0177 | -0.0015 | 0.2592 |
| Globex IB | Play 3 — IB Fade | 18672 | 0.0567 | 0.0181 | 0.8855 |
| London IB | Play 1 — IB Breakout | 37344 | 0.4006 | 0.0868 | 1.1228 |
| London IB | Play 2 — IB Retest | 37344 | 0.0326 | 0.0111 | 0.335 |
| London IB | Play 3 — IB Fade | 37344 | 0.0833 | 0.0171 | 0.9027 |
| Midnight OR | Play 1 — IB Breakout | 18640 | 0.7426 | 0.1751 | 1.6815 |
| Midnight OR | Play 2 — IB Retest | 18640 | 0.3 | 0.0219 | 1.0322 |
| Midnight OR | Play 3 — IB Fade | 18640 | 0.232 | 0.0363 | 1.2119 |
| NY AM IB | Play 1 — IB Breakout | 18680 | 0.4416 | 0.0831 | 1.0925 |
| NY AM IB | Play 2 — IB Retest | 18680 | 0.059 | 0.033 | 0.4631 |
| NY AM IB | Play 3 — IB Fade | 18680 | 0.1093 | 0.0231 | 1.0096 |
| NY PM IB | Play 1 — IB Breakout | 18300 | 0.3345 | 0.07 | 0.9396 |
| NY PM IB | Play 2 — IB Retest | 18300 | 0.0249 | 0.0135 | 0.2828 |
| NY PM IB | Play 3 — IB Fade | 18300 | 0.0703 | 0.0238 | 0.9618 |
| Tokyo IB | Play 1 — IB Breakout | 37260 | 0.6037 | 0.1269 | 1.3626 |
| Tokyo IB | Play 2 — IB Retest | 37260 | 0.1232 | 0.007 | 0.6542 |
| Tokyo IB | Play 3 — IB Fade | 37260 | 0.1626 | 0.0308 | 1.1536 |


### GC1 — By Target Level (extension multiplier)

| Play | Target | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Play 1 — IB Breakout | 0.25x | 37224 | 0.7044 | 0.0881 | 1.9246 |
| Play 1 — IB Breakout | 0.5x | 37224 | 0.5208 | 0.1041 | 1.4402 |
| Play 1 — IB Breakout | 0.75x | 37224 | 0.3847 | 0.1041 | 1.1534 |
| Play 1 — IB Breakout | 1.0x | 37224 | 0.2943 | 0.1132 | 0.9772 |
| Play 2 — IB Retest | 0.25x | 37224 | 0.1305 | 0.014 | 0.7866 |
| Play 2 — IB Retest | 0.5x | 37224 | 0.0961 | 0.0121 | 0.6802 |
| Play 2 — IB Retest | 0.75x | 37224 | 0.0725 | 0.0114 | 0.5829 |
| Play 2 — IB Retest | 1.0x | 37224 | 0.0579 | 0.0141 | 0.5238 |
| Play 3 — IB Fade | 0.25x | 37224 | 0.1076 | 0.0571 | 1.1069 |
| Play 3 — IB Fade | 0.5x | 37224 | 0.1295 | 0.0202 | 1.006 |
| Play 3 — IB Fade | 0.75x | 37224 | 0.1285 | 0.0131 | 1.0156 |
| Play 3 — IB Fade | 1.0x | 37224 | 0.1146 | 0.0082 | 1.0246 |


### GC1 — By Year

| Year | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| 2008 | Play 1 — IB Breakout | 7420 | 0.4753 | 0.1047 | 1.2407 |
| 2008 | Play 2 — IB Retest | 7420 | 0.083 | 0.0169 | 0.6059 |
| 2008 | Play 3 — IB Fade | 7420 | 0.1144 | 0.0294 | 1.0581 |
| 2009 | Play 1 — IB Breakout | 7120 | 0.469 | 0.0893 | 1.1747 |
| 2009 | Play 2 — IB Retest | 7120 | 0.083 | 0.0064 | 0.5726 |
| 2009 | Play 3 — IB Fade | 7120 | 0.1159 | 0.0254 | 1.0732 |
| 2010 | Play 1 — IB Breakout | 8176 | 0.4704 | 0.1006 | 1.1757 |
| 2010 | Play 2 — IB Retest | 8176 | 0.0843 | 0.0051 | 0.5918 |
| 2010 | Play 3 — IB Fade | 8176 | 0.1114 | 0.0204 | 1.0054 |
| 2011 | Play 1 — IB Breakout | 8224 | 0.4722 | 0.0903 | 1.1717 |
| 2011 | Play 2 — IB Retest | 8224 | 0.0845 | 0.0124 | 0.5714 |
| 2011 | Play 3 — IB Fade | 8224 | 0.1179 | 0.0224 | 1.036 |
| 2012 | Play 1 — IB Breakout | 8212 | 0.4827 | 0.1213 | 1.3289 |
| 2012 | Play 2 — IB Retest | 8212 | 0.0968 | 0.0489 | 0.7302 |
| 2012 | Play 3 — IB Fade | 8212 | 0.1142 | 0.0153 | 0.9905 |
| 2013 | Play 1 — IB Breakout | 8144 | 0.4785 | 0.1033 | 1.3097 |
| 2013 | Play 2 — IB Retest | 8144 | 0.0918 | 0.0313 | 0.7288 |
| 2013 | Play 3 — IB Fade | 8144 | 0.1178 | 0.0405 | 1.195 |
| 2014 | Play 1 — IB Breakout | 8084 | 0.4807 | 0.1075 | 1.3129 |
| 2014 | Play 2 — IB Retest | 8084 | 0.0901 | 0.0219 | 0.6423 |
| 2014 | Play 3 — IB Fade | 8084 | 0.1199 | 0.0297 | 1.1296 |
| 2015 | Play 1 — IB Breakout | 8032 | 0.4614 | 0.0828 | 1.1797 |
| 2015 | Play 2 — IB Retest | 8032 | 0.087 | -0.022 | 0.5809 |
| 2015 | Play 3 — IB Fade | 8032 | 0.1333 | 0.0472 | 1.2159 |
| 2016 | Play 1 — IB Breakout | 8224 | 0.4809 | 0.1067 | 1.2652 |
| 2016 | Play 2 — IB Retest | 8224 | 0.0845 | -0.0038 | 0.5982 |
| 2016 | Play 3 — IB Fade | 8224 | 0.1167 | 0.0107 | 0.9637 |
| 2017 | Play 1 — IB Breakout | 8200 | 0.4751 | 0.1161 | 1.3419 |
| 2017 | Play 2 — IB Retest | 8200 | 0.0789 | -0.0024 | 0.5961 |
| 2017 | Play 3 — IB Fade | 8200 | 0.1121 | 0.0233 | 0.9885 |
| 2018 | Play 1 — IB Breakout | 8228 | 0.4985 | 0.13 | 1.3901 |
| 2018 | Play 2 — IB Retest | 8228 | 0.0839 | -0.0021 | 0.5944 |
| 2018 | Play 3 — IB Fade | 8228 | 0.1146 | 0.0088 | 0.9084 |
| 2019 | Play 1 — IB Breakout | 8228 | 0.4724 | 0.1203 | 1.3158 |
| 2019 | Play 2 — IB Retest | 8228 | 0.0779 | -0.0059 | 0.595 |
| 2019 | Play 3 — IB Fade | 8228 | 0.1076 | 0.0032 | 0.8783 |
| 2020 | Play 1 — IB Breakout | 8256 | 0.4748 | 0.1001 | 1.2429 |
| 2020 | Play 2 — IB Retest | 8256 | 0.0896 | 0.0271 | 0.6533 |
| 2020 | Play 3 — IB Fade | 8256 | 0.1269 | 0.0294 | 1.0831 |
| 2021 | Play 1 — IB Breakout | 8228 | 0.468 | 0.0901 | 1.177 |
| 2021 | Play 2 — IB Retest | 8228 | 0.0922 | -0.0038 | 0.6268 |
| 2021 | Play 3 — IB Fade | 8228 | 0.1316 | 0.0423 | 1.2227 |
| 2022 | Play 1 — IB Breakout | 8212 | 0.4844 | 0.0896 | 1.1496 |
| 2022 | Play 2 — IB Retest | 8212 | 0.098 | 0.0093 | 0.6708 |
| 2022 | Play 3 — IB Fade | 8212 | 0.1338 | 0.0293 | 1.1116 |
| 2023 | Play 1 — IB Breakout | 8012 | 0.4633 | 0.0908 | 1.1579 |
| 2023 | Play 2 — IB Retest | 8012 | 0.0915 | 0.0122 | 0.6197 |
| 2023 | Play 3 — IB Fade | 8012 | 0.1287 | 0.023 | 1.0177 |
| 2024 | Play 1 — IB Breakout | 8276 | 0.4877 | 0.1057 | 1.2569 |
| 2024 | Play 2 — IB Retest | 8276 | 0.1119 | 0.0468 | 0.7471 |
| 2024 | Play 3 — IB Fade | 8276 | 0.1218 | 0.0242 | 1.077 |
| 2025 | Play 1 — IB Breakout | 8108 | 0.4725 | 0.0989 | 1.1826 |
| 2025 | Play 2 — IB Retest | 8108 | 0.0883 | 0.0153 | 0.6201 |
| 2025 | Play 3 — IB Fade | 8108 | 0.1216 | 0.0231 | 1.0817 |
| 2026 | Play 1 — IB Breakout | 3512 | 0.4735 | 0.0854 | 1.119 |
| 2026 | Play 2 — IB Retest | 3512 | 0.1068 | 0.053 | 0.7157 |
| 2026 | Play 3 — IB Fade | 3512 | 0.1216 | 0.0185 | 1.0234 |


### GC1 — By Month (aggregated across all years)

| Month | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Jan | Play 1 — IB Breakout | 11524 | 0.4852 | 0.1213 | 1.3299 |
| Jan | Play 2 — IB Retest | 11524 | 0.0891 | 0.0243 | 0.6612 |
| Jan | Play 3 — IB Fade | 11524 | 0.1099 | 0.0108 | 0.9323 |
| Feb | Play 1 — IB Breakout | 12116 | 0.4776 | 0.1032 | 1.2698 |
| Feb | Play 2 — IB Retest | 12116 | 0.091 | 0.0183 | 0.6634 |
| Feb | Play 3 — IB Fade | 12116 | 0.1129 | 0.0218 | 0.9982 |
| Mar | Play 1 — IB Breakout | 13144 | 0.488 | 0.1232 | 1.3545 |
| Mar | Play 2 — IB Retest | 13144 | 0.0999 | 0.0488 | 0.7534 |
| Mar | Play 3 — IB Fade | 13144 | 0.1163 | 0.0254 | 1.0758 |
| Apr | Play 1 — IB Breakout | 12332 | 0.4728 | 0.1037 | 1.2474 |
| Apr | Play 2 — IB Retest | 12332 | 0.0833 | 0.0094 | 0.5906 |
| Apr | Play 3 — IB Fade | 12332 | 0.122 | 0.0249 | 1.0418 |
| May | Play 1 — IB Breakout | 13276 | 0.4828 | 0.1009 | 1.2314 |
| May | Play 2 — IB Retest | 13276 | 0.0862 | -0.0017 | 0.6009 |
| May | Play 3 — IB Fade | 13276 | 0.1199 | 0.0195 | 1.016 |
| Jun | Play 1 — IB Breakout | 12900 | 0.4674 | 0.085 | 1.1425 |
| Jun | Play 2 — IB Retest | 12900 | 0.0819 | -0.0223 | 0.5437 |
| Jun | Play 3 — IB Fade | 12900 | 0.1217 | 0.0288 | 1.1047 |
| Jul | Play 1 — IB Breakout | 13016 | 0.4858 | 0.1045 | 1.2719 |
| Jul | Play 2 — IB Retest | 13016 | 0.0973 | 0.0245 | 0.6863 |
| Jul | Play 3 — IB Fade | 13016 | 0.1301 | 0.0276 | 1.0712 |
| Aug | Play 1 — IB Breakout | 12468 | 0.4571 | 0.0845 | 1.1517 |
| Aug | Play 2 — IB Retest | 12468 | 0.0818 | -0.0054 | 0.5787 |
| Aug | Play 3 — IB Fade | 12468 | 0.1264 | 0.0343 | 1.1445 |
| Sep | Play 1 — IB Breakout | 11552 | 0.4911 | 0.1252 | 1.3521 |
| Sep | Play 2 — IB Retest | 11552 | 0.0966 | 0.0339 | 0.7017 |
| Sep | Play 3 — IB Fade | 11552 | 0.1202 | 0.0197 | 0.9946 |
| Oct | Play 1 — IB Breakout | 12312 | 0.4613 | 0.0862 | 1.1421 |
| Oct | Play 2 — IB Retest | 12312 | 0.083 | -0.0129 | 0.5752 |
| Oct | Play 3 — IB Fade | 12312 | 0.1157 | 0.0257 | 1.0703 |
| Nov | Play 1 — IB Breakout | 12196 | 0.4701 | 0.095 | 1.213 |
| Nov | Play 2 — IB Retest | 12196 | 0.0881 | 0.0203 | 0.6322 |
| Nov | Play 3 — IB Fade | 12196 | 0.1205 | 0.0221 | 1.0284 |
| Dec | Play 1 — IB Breakout | 12060 | 0.4736 | 0.0982 | 1.1839 |
| Dec | Play 2 — IB Retest | 12060 | 0.0926 | 0.0198 | 0.6261 |
| Dec | Play 3 — IB Fade | 12060 | 0.1244 | 0.0341 | 1.1545 |


### GC1 — By Day of Week

| Day | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Mon | Play 1 — IB Breakout | 29492 | 0.4567 | 0.1084 | 1.2811 |
| Mon | Play 2 — IB Retest | 29492 | 0.0807 | 0.0179 | 0.6248 |
| Mon | Play 3 — IB Fade | 29492 | 0.1109 | 0.0183 | 0.9927 |
| Tue | Play 1 — IB Breakout | 30128 | 0.4903 | 0.1146 | 1.3115 |
| Tue | Play 2 — IB Retest | 30128 | 0.0937 | 0.0246 | 0.696 |
| Tue | Play 3 — IB Fade | 30128 | 0.118 | 0.0243 | 1.0414 |
| Wed | Play 1 — IB Breakout | 30056 | 0.4799 | 0.0928 | 1.172 |
| Wed | Play 2 — IB Retest | 30056 | 0.0955 | 0.0117 | 0.6239 |
| Wed | Play 3 — IB Fade | 30056 | 0.128 | 0.0329 | 1.1333 |
| Thu | Play 1 — IB Breakout | 29944 | 0.4767 | 0.0996 | 1.2189 |
| Thu | Play 2 — IB Retest | 29944 | 0.0866 | 0.0032 | 0.6083 |
| Thu | Play 3 — IB Fade | 29944 | 0.1212 | 0.0234 | 1.0356 |
| Fri | Play 1 — IB Breakout | 29276 | 0.4762 | 0.0965 | 1.2137 |
| Fri | Play 2 — IB Retest | 29276 | 0.0896 | 0.0069 | 0.6133 |
| Fri | Play 3 — IB Fade | 29276 | 0.1223 | 0.0242 | 1.0584 |


## 3. Regime-Adjusted Statistics


### NQ1 — By Regime

| Regime | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| trend | Play 1 — IB Breakout | 86316 | 0.4955 | 0.1012 | 1.2297 |
| trend | Play 2 — IB Retest | 86316 | 0.1044 | 0.025 | 0.6966 |
| trend | Play 3 — IB Fade | 86316 | 0.1304 | 0.0281 | 1.1105 |
| skip | Play 1 — IB Breakout | 58964 | 0.4784 | 0.0804 | 1.0672 |
| skip | Play 2 — IB Retest | 58964 | 0.0921 | 0.0159 | 0.6167 |
| skip | Play 3 — IB Fade | 58964 | 0.1283 | 0.0288 | 1.0788 |
| normal | Play 1 — IB Breakout | 12512 | 0.3686 | 0.0506 | 0.8727 |
| normal | Play 2 — IB Retest | 12512 | 0.0365 | -0.0224 | 0.3412 |
| normal | Play 3 — IB Fade | 12512 | 0.0864 | 0.025 | 1.0271 |
| range | Play 1 — IB Breakout | 8224 | 0.3577 | 0.0514 | 0.8102 |
| range | Play 2 — IB Retest | 8224 | 0.0393 | -0.0036 | 0.3466 |
| range | Play 3 — IB Fade | 8224 | 0.0773 | 0.0166 | 0.9231 |


### ES1 — By Regime

| Regime | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| trend | Play 1 — IB Breakout | 89732 | 0.5131 | 0.1197 | 1.3439 |
| trend | Play 2 — IB Retest | 89732 | 0.1121 | 0.0271 | 0.7282 |
| trend | Play 3 — IB Fade | 89732 | 0.1377 | -0.0007 | 0.9092 |
| skip | Play 1 — IB Breakout | 53444 | 0.473 | 0.0836 | 1.0727 |
| skip | Play 2 — IB Retest | 53444 | 0.0924 | 0.0192 | 0.6223 |
| skip | Play 3 — IB Fade | 53444 | 0.1268 | 0.0123 | 0.9495 |
| normal | Play 1 — IB Breakout | 13392 | 0.4003 | 0.0695 | 0.9788 |
| normal | Play 2 — IB Retest | 13392 | 0.0473 | -0.0006 | 0.401 |
| normal | Play 3 — IB Fade | 13392 | 0.0938 | 0.0128 | 0.9208 |
| range | Play 1 — IB Breakout | 7784 | 0.3763 | 0.038 | 0.8212 |
| range | Play 2 — IB Retest | 7784 | 0.0457 | -0.0278 | 0.358 |
| range | Play 3 — IB Fade | 7784 | 0.0937 | 0.0196 | 0.9825 |


### YM1 — By Regime

| Regime | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| normal | Play 1 — IB Breakout | 13216 | 0.3878 | 0.0551 | 0.9338 |
| normal | Play 2 — IB Retest | 13216 | 0.0487 | 0.0 | 0.4217 |
| normal | Play 3 — IB Fade | 13216 | 0.0872 | 0.0223 | 0.9816 |
| skip | Play 1 — IB Breakout | 52212 | 0.4723 | 0.0707 | 1.0336 |
| skip | Play 2 — IB Retest | 52212 | 0.0931 | 0.0115 | 0.5993 |
| skip | Play 3 — IB Fade | 52212 | 0.1279 | 0.032 | 1.128 |
| range | Play 1 — IB Breakout | 8624 | 0.3648 | 0.0431 | 0.834 |
| range | Play 2 — IB Retest | 8624 | 0.0452 | -0.0104 | 0.3819 |
| range | Play 3 — IB Fade | 8624 | 0.09 | 0.0139 | 0.9493 |
| trend | Play 1 — IB Breakout | 74376 | 0.4877 | 0.088 | 1.1565 |
| trend | Play 2 — IB Retest | 74376 | 0.1049 | 0.0175 | 0.6724 |
| trend | Play 3 — IB Fade | 74376 | 0.1344 | 0.032 | 1.1458 |


### RTY1 — By Regime

| Regime | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| skip | Play 1 — IB Breakout | 26116 | 0.4635 | 0.0738 | 1.0205 |
| skip | Play 2 — IB Retest | 26116 | 0.0864 | 0.0195 | 0.5914 |
| skip | Play 3 — IB Fade | 26116 | 0.119 | 0.0273 | 1.0608 |
| normal | Play 1 — IB Breakout | 7804 | 0.3787 | 0.0715 | 0.9744 |
| normal | Play 2 — IB Retest | 7804 | 0.0406 | 0.0026 | 0.4275 |
| normal | Play 3 — IB Fade | 7804 | 0.0774 | 0.0134 | 0.9194 |
| trend | Play 1 — IB Breakout | 28472 | 0.5073 | 0.0849 | 1.1334 |
| trend | Play 2 — IB Retest | 28472 | 0.1066 | 0.0001 | 0.6655 |
| trend | Play 3 — IB Fade | 28472 | 0.1383 | 0.0355 | 1.1796 |
| range | Play 1 — IB Breakout | 8564 | 0.3475 | 0.0476 | 0.8169 |
| range | Play 2 — IB Retest | 8564 | 0.0353 | -0.005 | 0.326 |
| range | Play 3 — IB Fade | 8564 | 0.0778 | 0.0131 | 0.9361 |


### CL1 — By Regime

| Regime | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| range | Play 1 — IB Breakout | 44564 | 0.4107 | 0.0837 | 1.1429 |
| range | Play 2 — IB Retest | 44564 | 0.0592 | 0.0087 | 0.5111 |
| range | Play 3 — IB Fade | 44564 | 0.0977 | 0.0219 | 1.0347 |
| skip | Play 1 — IB Breakout | 53568 | 0.4441 | 0.0894 | 1.1605 |
| skip | Play 2 — IB Retest | 53568 | 0.0873 | 0.0077 | 0.6387 |
| skip | Play 3 — IB Fade | 53568 | 0.1119 | 0.0195 | 1.0277 |
| trend | Play 1 — IB Breakout | 28436 | 0.6121 | 0.1511 | 1.5732 |
| trend | Play 2 — IB Retest | 28436 | 0.1717 | -0.0099 | 0.8448 |
| trend | Play 3 — IB Fade | 28436 | 0.168 | 0.0212 | 1.0998 |
| normal | Play 1 — IB Breakout | 18496 | 0.4913 | 0.0952 | 1.2267 |
| normal | Play 2 — IB Retest | 18496 | 0.0923 | -0.0112 | 0.5985 |
| normal | Play 3 — IB Fade | 18496 | 0.1296 | 0.03 | 1.1423 |


### GC1 — By Regime

| Regime | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| trend | Play 1 — IB Breakout | 78044 | 0.5111 | 0.1179 | 1.33 |
| trend | Play 2 — IB Retest | 78044 | 0.1008 | 0.0084 | 0.6636 |
| trend | Play 3 — IB Fade | 78044 | 0.1303 | 0.0252 | 1.0702 |
| skip | Play 1 — IB Breakout | 50772 | 0.484 | 0.0959 | 1.1934 |
| skip | Play 2 — IB Retest | 50772 | 0.0946 | 0.0191 | 0.6429 |
| skip | Play 3 — IB Fade | 50772 | 0.1258 | 0.0288 | 1.089 |
| normal | Play 1 — IB Breakout | 12300 | 0.3368 | 0.0656 | 0.9927 |
| normal | Play 2 — IB Retest | 12300 | 0.0291 | 0.0162 | 0.3335 |
| normal | Play 3 — IB Fade | 12300 | 0.0674 | 0.0085 | 0.8061 |
| range | Play 1 — IB Breakout | 6380 | 0.2522 | 0.0398 | 0.7751 |
| range | Play 2 — IB Retest | 6380 | 0.0221 | 0.0168 | 0.3255 |
| range | Play 3 — IB Fade | 6380 | 0.0516 | 0.0143 | 0.8015 |


## 4. Top Filter Lifts (Phase 4a)


### Top 15 filters by lift vs without-flag (all targets pooled)

| Symbol | Target | Filter | Lift | WR (flag on) | WR (flag off) | N (flag on) |
|---|---|---|---|---|---|---|
| NQ1 | realized_dir_break | break_vs_avwap_0930 | 0.5544 | 0.5571 | 0.0027 | 19976 |
| NQ1 | bias_correct_combined_05x | break_vs_avwap_0930 | 0.3854 | 0.3872 | 0.0018 | 19976 |
| NQ1 | bias_correct_combined_05x | trend_aligned_with_break | 0.3837 | 0.4851 | 0.1013 | 26032 |
| NQ1 | play1_result | break_vs_avwap_0930 | 0.3244 | 0.3269 | 0.0025 | 19976 |
| NQ1 | realized_dir_break | ib_news_distorted | 0.1921 | 0.6667 | 0.4746 | 15 |
| NQ1 | play3_result | break_vs_avwap_0930 | 0.1536 | 0.1543 | 0.0007 | 19976 |
| NQ1 | realized_dir_break | trend_misaligned_with_break | 0.1331 | 0.5723 | 0.4392 | 11059 |
| NQ1 | play2_result | break_vs_avwap_0930 | 0.1123 | 0.1123 | 0.0 | 19976 |
| NQ1 | realized_dir_break | trend_aligned_with_break | 0.1046 | 0.5137 | 0.4091 | 26032 |
| NQ1 | bias_correct_combined_05x | ib_news_break | 0.0935 | 0.4353 | 0.3418 | 85 |
| NQ1 | play1_result | trend_misaligned_with_break | 0.09 | 0.3545 | 0.2645 | 11059 |
| NQ1 | play1_result | ib_vcp_3day_contracting | 0.0889 | 0.3625 | 0.2736 | 6947 |
| NQ1 | realized_dir_break | fail_setup_score | 0.0791 | 0.5446 | 0.4654 | 4859 |
| NQ1 | realized_dir_break | higher_highs_ib | 0.0708 | 0.4797 | 0.4089 | 38557 |
| NQ1 | bias_correct_combined_05x | avwap_aligned | 0.0682 | 0.3424 | 0.2742 | 41256 |


## 5. MAE-Calibrated Stops (Phase 5.1)


### Sample: NY AM IB / ET_fixed, by play × target

| Symbol | Play | Target | P95 MAE | P99 MAE | Stop (R) | WR @ stop | Exp @ stop | N win | N total |
|---|---|---|---|---|---|---|---|---|---|
| NQ1 | 1 | 0.25 | 0.3105759135201318 | 0.5492501617504584 | 4.9644 | 0.7289 | 0.1445 | 3847 | 5278 |
| NQ1 | 1 | 0.5 | 0.3313291295794839 | 0.5640041976781174 | 2.8949 | 0.5256 | 0.2035 | 2774 | 5278 |
| NQ1 | 1 | 0.75 | 0.3284676191463123 | 0.5482571841734418 | 2.3029 | 0.3554 | 0.2343 | 1876 | 5278 |
| NQ1 | 1 | 1.0 | 0.3018482782547232 | 0.4945458284625339 | 1.9751 | 0.2442 | 0.2804 | 1289 | 5278 |
| NQ1 | 2 | 0.25 | 0.21802592744852656 | 0.44480020994344827 | 0.218 | 0.1057 | 0.0713 | 558 | 5278 |
| NQ1 | 2 | 0.5 | 0.22100575040974674 | 0.463364456513574 | 0.221 | 0.0661 | 0.0693 | 349 | 5278 |
| NQ1 | 2 | 0.75 | 0.1962308062635155 | 0.34434040668777766 | 0.1962 | 0.0423 | 0.0929 | 223 | 5278 |
| NQ1 | 2 | 1.0 | 0.18593166790688911 | 0.32639951116146687 | 0.1859 | 0.0275 | 0.0975 | 145 | 5278 |
| NQ1 | 3 | 0.25 | 0.1479280094175159 | 0.22230748364754943 | 0.1479 | 0.1199 | 0.1146 | 633 | 5278 |
| NQ1 | 3 | 0.5 | 0.20573869864706382 | 0.3799681585476813 | 0.2057 | 0.1302 | 0.0744 | 687 | 5278 |
| NQ1 | 3 | 0.75 | 0.25392500813474206 | 0.5469453949692474 | 0.2539 | 0.1209 | 0.0547 | 638 | 5278 |
| NQ1 | 3 | 1.0 | 0.306369426214452 | 0.4780750679006782 | 0.3064 | 0.0928 | 0.0303 | 490 | 5278 |
| ES1 | 1 | 0.25 | 0.2849539131212066 | 0.4940728727905864 | 4.9241 | 0.7807 | 0.1739 | 4116 | 5272 |
| ES1 | 1 | 0.5 | 0.3303305055863963 | 0.5479838324563238 | 3.0152 | 0.5797 | 0.2294 | 3056 | 5272 |
| ES1 | 1 | 0.75 | 0.33119222910517976 | 0.5773639905046082 | 2.2524 | 0.4207 | 0.2711 | 2218 | 5272 |
| ES1 | 1 | 1.0 | 0.317255860154513 | 0.5733396047072741 | 1.9548 | 0.3044 | 0.3091 | 1605 | 5272 |
| ES1 | 2 | 0.25 | 0.2138131229365617 | 0.4051538283279326 | 0.2138 | 0.1309 | 0.0908 | 690 | 5272 |
| ES1 | 2 | 0.5 | 0.21444286268480725 | 0.3342121815735272 | 0.2144 | 0.0905 | 0.0956 | 477 | 5272 |
| ES1 | 2 | 0.75 | 0.20225367544886236 | 0.28509265999987843 | 0.2023 | 0.0634 | 0.112 | 334 | 5272 |
| ES1 | 2 | 1.0 | 0.19708998918093298 | 0.24847626640829518 | 0.1971 | 0.0429 | 0.1121 | 226 | 5272 |
| ES1 | 3 | 0.25 | 0.13990567488708314 | 0.19543944152509457 | 0.1399 | 0.1297 | 0.1074 | 684 | 5272 |
| ES1 | 3 | 0.5 | 0.21691875055348012 | 0.34729567449811044 | 0.2169 | 0.1618 | 0.0755 | 853 | 5272 |
| ES1 | 3 | 0.75 | 0.267200979319498 | 0.4609631244796968 | 0.2672 | 0.1383 | 0.0503 | 729 | 5272 |
| ES1 | 3 | 1.0 | 0.31366745776269706 | 0.6149764592320182 | 0.3137 | 0.1149 | 0.0315 | 606 | 5272 |
| YM1 | 1 | 0.25 | 0.31791171652369277 | 0.5972984152173578 | 4.9157 | 0.7413 | 0.164 | 3498 | 4719 |
| YM1 | 1 | 0.5 | 0.34705156952200067 | 0.6564082039587249 | 2.9346 | 0.5366 | 0.2357 | 2532 | 4719 |
| YM1 | 1 | 0.75 | 0.3644802632860846 | 0.7095629878276504 | 2.3457 | 0.3723 | 0.2529 | 1757 | 4719 |
| YM1 | 1 | 1.0 | 0.37199981996144893 | 0.8773189801726348 | 2.1951 | 0.2632 | 0.2634 | 1242 | 4719 |
| YM1 | 2 | 0.25 | 0.23998964555634722 | 0.49625434390028234 | 0.24 | 0.1225 | 0.1025 | 578 | 4719 |
| YM1 | 2 | 0.5 | 0.24760785236804053 | 0.4966893799717048 | 0.2476 | 0.0784 | 0.1001 | 370 | 4719 |
| YM1 | 2 | 0.75 | 0.23655259882292806 | 0.47375098869055304 | 0.2366 | 0.0528 | 0.1101 | 249 | 4719 |
| YM1 | 2 | 1.0 | 0.24030334957784985 | 0.4676301570549525 | 0.2403 | 0.0354 | 0.11 | 167 | 4719 |
| YM1 | 3 | 0.25 | 0.13270250042450105 | 0.2791912322454109 | 0.1327 | 0.1187 | 0.1416 | 560 | 4719 |
| YM1 | 3 | 0.5 | 0.24409218643338623 | 0.3912799313550078 | 0.2441 | 0.1333 | 0.0675 | 629 | 4719 |
| YM1 | 3 | 0.75 | 0.29033573415701835 | 0.585203693408007 | 0.2903 | 0.1263 | 0.0538 | 596 | 4719 |
| YM1 | 3 | 1.0 | 0.32088474809681133 | 0.6934513235964742 | 0.3209 | 0.1064 | 0.0375 | 502 | 4719 |
| RTY1 | 1 | 0.25 | 0.5102321110041104 | 0.8177151841833409 | 4.6534 | 0.6932 | 0.1666 | 1579 | 2278 |
| RTY1 | 1 | 0.5 | 0.5261538715395082 | 0.8415324483820145 | 2.4863 | 0.4802 | 0.2435 | 1094 | 2278 |
| RTY1 | 1 | 0.75 | 0.4748650422128467 | 0.8047197144091721 | 1.8656 | 0.3161 | 0.3029 | 720 | 2278 |
| RTY1 | 1 | 1.0 | 0.4828817985316395 | 0.739843388097488 | 1.7931 | 0.2068 | 0.3205 | 471 | 2278 |
| RTY1 | 2 | 0.25 | 0.3407218756536673 | 0.44451345216589305 | 0.3407 | 0.0896 | 0.1112 | 204 | 2278 |
| RTY1 | 2 | 0.5 | 0.3056230058076687 | 0.3893001375531854 | 0.3056 | 0.0571 | 0.1408 | 130 | 2278 |
| RTY1 | 2 | 0.75 | 0.3317346846758914 | 0.41479586374103566 | 0.3317 | 0.032 | 0.1252 | 73 | 2278 |
| RTY1 | 2 | 1.0 | 0.319834716098428 | 0.373647786030074 | 0.3198 | 0.0206 | 0.1329 | 47 | 2278 |
| RTY1 | 3 | 0.25 | 0.21865032990229866 | 0.3550738847835183 | 0.2187 | 0.1133 | 0.1352 | 258 | 2278 |
| RTY1 | 3 | 0.5 | 0.37794748078514834 | 0.5620977574075589 | 0.3779 | 0.1168 | 0.0561 | 266 | 2278 |
| RTY1 | 3 | 0.75 | 0.43750941276760963 | 0.6229716832755497 | 0.4375 | 0.0913 | 0.0392 | 208 | 2278 |
| RTY1 | 3 | 1.0 | 0.4087873422733322 | 0.7847937114636403 | 0.4088 | 0.0698 | 0.028 | 159 | 2278 |
| CL1 | 1 | 0.25 | 1.0031573216292882 | 2.405459601140467 | 5.1571 | 0.8037 | 0.1764 | 3690 | 4591 |
| CL1 | 1 | 0.5 | 1.0722879561591812 | 2.571880678184323 | 3.2433 | 0.6262 | 0.2672 | 2875 | 4591 |
| CL1 | 1 | 0.75 | 1.0863546916787108 | 2.57837448188862 | 2.438 | 0.484 | 0.3122 | 2222 | 4591 |
| CL1 | 1 | 1.0 | 1.0682986151271014 | 2.314186331673381 | 2.1431 | 0.3712 | 0.3476 | 1704 | 4591 |
| CL1 | 2 | 0.25 | 0.6680079212053912 | 2.0983148536410767 | 39.2054 | 0.1586 | 0.1242 | 728 | 4591 |
| CL1 | 2 | 0.5 | 0.6791989569607797 | 2.5661856348605108 | 34.7173 | 0.1144 | 0.1336 | 525 | 4591 |
| CL1 | 2 | 0.75 | 0.6900246437372699 | 2.978116505095387 | 31.541 | 0.0852 | 0.1439 | 391 | 4591 |
| CL1 | 2 | 1.0 | 0.6051629474490172 | 2.9828978563360264 | 27.0931 | 0.0629 | 0.1832 | 289 | 4591 |
| CL1 | 3 | 0.25 | 0.42948089474975587 | 0.7728201206078242 | 0.4295 | 0.1252 | 0.1337 | 575 | 4591 |
| CL1 | 3 | 0.5 | 0.7128997560885166 | 2.9569633263572084 | 0.7129 | 0.1649 | 0.0912 | 757 | 4591 |
| CL1 | 3 | 0.75 | 0.8424596273943591 | 2.2520475131683084 | 0.8425 | 0.1649 | 0.067 | 757 | 4591 |
| CL1 | 3 | 1.0 | 0.8409508517475821 | 2.1661036299780854 | 0.841 | 0.1442 | 0.0511 | 662 | 4591 |
| GC1 | 1 | 0.25 | 0.19828103753749168 | 0.39941814668000647 | 4.1619 | 0.6887 | 0.1706 | 3216 | 4670 |
| GC1 | 1 | 0.5 | 0.21758817432916921 | 0.4160803627742994 | 2.7196 | 0.4882 | 0.253 | 2280 | 4670 |
| GC1 | 1 | 0.75 | 0.21002474700707752 | 0.38560335220242953 | 2.0311 | 0.3452 | 0.3048 | 1612 | 4670 |
| GC1 | 1 | 1.0 | 0.2092181517668473 | 0.33716605834266467 | 1.8493 | 0.2443 | 0.3281 | 1141 | 4670 |
| GC1 | 2 | 0.25 | 0.14806741682608307 | 0.2029077479312859 | 0.1481 | 0.1002 | 0.1362 | 468 | 4670 |
| GC1 | 2 | 0.5 | 0.15936510876069526 | 0.20109660959361708 | 0.1594 | 0.063 | 0.1254 | 294 | 4670 |
| GC1 | 2 | 0.75 | 0.15782849918454112 | 0.19985086229271992 | 0.1578 | 0.0422 | 0.1288 | 197 | 4670 |
| GC1 | 2 | 1.0 | 0.14334971236983557 | 0.17316125505132313 | 0.1433 | 0.0308 | 0.1468 | 144 | 4670 |
| GC1 | 3 | 0.25 | 0.1064401106171797 | 0.14926490010410964 | 0.1064 | 0.1113 | 0.146 | 520 | 4670 |
| GC1 | 3 | 0.5 | 0.14803393434958587 | 0.2537228640251283 | 0.148 | 0.1248 | 0.0974 | 583 | 4670 |
| GC1 | 3 | 0.75 | 0.18195324217544873 | 0.30358151142816003 | 0.182 | 0.1143 | 0.057 | 534 | 4670 |
| GC1 | 3 | 1.0 | 0.22687624929319303 | 0.39270342436177497 | 0.2269 | 0.0865 | 0.0263 | 404 | 4670 |


## 6. Optimal Profit Ladders (Phase 5.3)


### Sample: NY AM IB / ET_fixed, by play × target

| Symbol | Play | Target | TP1% | TP2% | TP3% | Runner% | Ladder Exp | Baseline Exp | N |
|---|---|---|---|---|---|---|---|---|---|
| NQ1 | 1 | 0.25 | 0.3 | 0.3 | 0.25 | 0.15 | 0.5116 | 0.0509 | 5278 |
| NQ1 | 1 | 0.5 | 0.3 | 0.3 | 0.25 | 0.15 | 0.3327 | 0.0621 | 5278 |
| NQ1 | 1 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.2393 | 0.0605 | 5278 |
| NQ1 | 1 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.2029 | 0.0654 | 5278 |
| NQ1 | 2 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0243 | -0.0157 | 5278 |
| NQ1 | 2 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0394 | -0.0188 | 5278 |
| NQ1 | 2 | 0.75 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0444 | -0.0174 | 5278 |
| NQ1 | 2 | 1.0 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0482 | -0.019 | 5278 |
| NQ1 | 3 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0415 | 0.045 | 5278 |
| NQ1 | 3 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | 0.032 | 0.0152 | 5278 |
| NQ1 | 3 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0658 | 0.0146 | 5278 |
| NQ1 | 3 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0613 | 0.0076 | 5278 |
| ES1 | 1 | 0.25 | 0.3 | 0.3 | 0.25 | 0.15 | 0.5546 | 0.0667 | 5272 |
| ES1 | 1 | 0.5 | 0.3 | 0.3 | 0.25 | 0.15 | 0.3478 | 0.0717 | 5272 |
| ES1 | 1 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.2403 | 0.0762 | 5272 |
| ES1 | 1 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.1851 | 0.0783 | 5272 |
| ES1 | 2 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0381 | -0.0195 | 5272 |
| ES1 | 2 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | -0.057 | -0.0194 | 5272 |
| ES1 | 2 | 0.75 | 0.25 | 0.25 | 0.25 | 0.25 | -0.063 | -0.0126 | 5272 |
| ES1 | 2 | 1.0 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0694 | -0.0164 | 5272 |
| ES1 | 3 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0718 | 0.0231 | 5272 |
| ES1 | 3 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | 0.0131 | 0.0029 | 5272 |
| ES1 | 3 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0521 | -0.0023 | 5272 |
| ES1 | 3 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0636 | -0.0014 | 5272 |
| YM1 | 1 | 0.25 | 0.3 | 0.3 | 0.25 | 0.15 | 0.5223 | 0.0542 | 4719 |
| YM1 | 1 | 0.5 | 0.3 | 0.3 | 0.25 | 0.15 | 0.3393 | 0.0662 | 4719 |
| YM1 | 1 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.2367 | 0.0627 | 4719 |
| YM1 | 1 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.19 | 0.0653 | 4719 |
| YM1 | 2 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0108 | 0.0019 | 4719 |
| YM1 | 2 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0255 | 0.002 | 4719 |
| YM1 | 2 | 0.75 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0336 | 0.0021 | 4719 |
| YM1 | 2 | 1.0 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0365 | 0.0035 | 4719 |
| YM1 | 3 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0529 | 0.0326 | 4719 |
| YM1 | 3 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | 0.0219 | 0.0067 | 4719 |
| YM1 | 3 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0697 | 0.0139 | 4719 |
| YM1 | 3 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0765 | 0.0122 | 4719 |
| RTY1 | 1 | 0.25 | 0.3 | 0.3 | 0.25 | 0.15 | 0.5037 | 0.0535 | 2278 |
| RTY1 | 1 | 0.5 | 0.3 | 0.3 | 0.25 | 0.15 | 0.3325 | 0.0618 | 2278 |
| RTY1 | 1 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.2583 | 0.0647 | 2278 |
| RTY1 | 1 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.2276 | 0.0662 | 2278 |
| RTY1 | 2 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | 0.0136 | 0.0122 | 2278 |
| RTY1 | 2 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | 0.003 | 0.0151 | 2278 |
| RTY1 | 2 | 0.75 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0006 | 0.0152 | 2278 |
| RTY1 | 2 | 1.0 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0011 | 0.0161 | 2278 |
| RTY1 | 3 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | -0.061 | 0.0183 | 2278 |
| RTY1 | 3 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | 0.0127 | -0.006 | 2278 |
| RTY1 | 3 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0436 | -0.0035 | 2278 |
| RTY1 | 3 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.053 | 0.0056 | 2278 |
| CL1 | 1 | 0.25 | 0.3 | 0.3 | 0.25 | 0.15 | 0.5981 | 0.0971 | 4591 |
| CL1 | 1 | 0.5 | 0.3 | 0.3 | 0.25 | 0.15 | 0.406 | 0.1207 | 4591 |
| CL1 | 1 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.2902 | 0.1326 | 4591 |
| CL1 | 1 | 1.0 | 0.25 | 0.25 | 0.25 | 0.25 | 0.2291 | 0.1417 | 4591 |
| CL1 | 2 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0129 | 0.0182 | 4591 |
| CL1 | 2 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0337 | 0.025 | 4591 |
| CL1 | 2 | 0.75 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0422 | 0.0331 | 4591 |
| CL1 | 2 | 1.0 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0458 | 0.0404 | 4591 |
| CL1 | 3 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0316 | 0.0596 | 4591 |
| CL1 | 3 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | 0.048 | 0.0378 | 4591 |
| CL1 | 3 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0768 | 0.0202 | 4591 |
| CL1 | 3 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0885 | 0.0161 | 4591 |
| GC1 | 1 | 0.25 | 0.3 | 0.3 | 0.25 | 0.15 | 0.5111 | 0.0731 | 4670 |
| GC1 | 1 | 0.5 | 0.3 | 0.3 | 0.25 | 0.15 | 0.338 | 0.0825 | 4670 |
| GC1 | 1 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.2522 | 0.0863 | 4670 |
| GC1 | 1 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.2179 | 0.0904 | 4670 |
| GC1 | 2 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | 0.0363 | 0.0356 | 4670 |
| GC1 | 2 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | 0.0203 | 0.0297 | 4670 |
| GC1 | 2 | 0.75 | 0.25 | 0.25 | 0.25 | 0.25 | 0.0158 | 0.0307 | 4670 |
| GC1 | 2 | 1.0 | 0.25 | 0.25 | 0.25 | 0.25 | 0.0158 | 0.0359 | 4670 |
| GC1 | 3 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | -0.0293 | 0.0465 | 4670 |
| GC1 | 3 | 0.5 | 0.25 | 0.25 | 0.25 | 0.25 | 0.0425 | 0.0244 | 4670 |
| GC1 | 3 | 0.75 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0616 | 0.0127 | 4670 |
| GC1 | 3 | 1.0 | 0.3 | 0.3 | 0.25 | 0.15 | 0.0617 | 0.0088 | 4670 |


## 7. Break Speed Statistics (Phase 5.4)


### Sample: NQ1, NY AM IB / ET_fixed, by play × speed bucket

| Play | Target | Speed | N | WR | Exp (R) | Mean Speed |
|---|---|---|---|---|---|---|
| 1 | 0.25 | very_slow | 1359 | 0.727 | 0.0529 | 0.2335 |
| 1 | 0.5 | very_slow | 1359 | 0.4908 | 0.0579 | 0.2335 |
| 1 | 0.75 | very_slow | 1359 | 0.3311 | 0.0646 | 0.2335 |
| 1 | 1.0 | very_slow | 1359 | 0.2369 | 0.0744 | 0.2335 |
| 2 | 0.25 | very_slow | 1359 | 0.0912 | 0.0019 | 0.2335 |
| 2 | 0.5 | very_slow | 1359 | 0.0478 | -0.0151 | 0.2335 |
| 2 | 0.75 | very_slow | 1359 | 0.0316 | -0.0187 | 0.2335 |
| 2 | 1.0 | very_slow | 1359 | 0.0235 | -0.0214 | 0.2335 |
| 3 | 0.25 | very_slow | 1359 | 0.1148 | 0.0514 | 0.2335 |
| 3 | 0.5 | very_slow | 1359 | 0.1185 | 0.03 | 0.2335 |
| 3 | 0.75 | very_slow | 1359 | 0.0979 | 0.0204 | 0.2335 |
| 3 | 1.0 | very_slow | 1359 | 0.0684 | 0.0046 | 0.2335 |
| 1 | 0.25 | very_fast | 1422 | 0.7975 | 0.0521 | 33.6979 |
| 1 | 0.5 | very_fast | 1422 | 0.6006 | 0.0737 | 33.6979 |
| 1 | 0.75 | very_fast | 1422 | 0.4065 | 0.0726 | 33.6979 |
| 1 | 1.0 | very_fast | 1422 | 0.2602 | 0.0608 | 33.6979 |
| 2 | 0.25 | very_fast | 1422 | 0.1217 | -0.0341 | 33.6979 |
| 2 | 0.5 | very_fast | 1422 | 0.0809 | -0.0307 | 33.6979 |
| 2 | 0.75 | very_fast | 1422 | 0.0492 | -0.0265 | 33.6979 |
| 2 | 1.0 | very_fast | 1422 | 0.0302 | -0.0234 | 33.6979 |
| 3 | 0.25 | very_fast | 1422 | 0.1414 | 0.0559 | 33.6979 |
| 3 | 0.5 | very_fast | 1422 | 0.1421 | 0.0164 | 33.6979 |
| 3 | 0.75 | very_fast | 1422 | 0.1301 | 0.0001 | 33.6979 |
| 3 | 1.0 | very_fast | 1422 | 0.1125 | 0.0028 | 33.6979 |
| 1 | 0.25 | moderate | 684 | 0.7427 | 0.0256 | 1.4352 |
| 1 | 0.5 | moderate | 684 | 0.5409 | 0.0476 | 1.4352 |
| 1 | 0.75 | moderate | 684 | 0.3494 | 0.0238 | 1.4352 |
| 1 | 1.0 | moderate | 684 | 0.2354 | 0.0294 | 1.4352 |
| 2 | 0.25 | moderate | 684 | 0.1257 | 0.0096 | 1.4352 |
| 2 | 0.5 | moderate | 684 | 0.0746 | -0.0026 | 1.4352 |
| 2 | 0.75 | moderate | 684 | 0.0453 | -0.0006 | 1.4352 |
| 2 | 1.0 | moderate | 684 | 0.0307 | -0.0016 | 1.4352 |
| 3 | 0.25 | moderate | 684 | 0.1506 | 0.105 | 1.4352 |
| 3 | 0.5 | moderate | 684 | 0.1447 | 0.0167 | 1.4352 |
| 3 | 0.75 | moderate | 684 | 0.1491 | 0.0204 | 1.4352 |
| 3 | 1.0 | moderate | 684 | 0.1067 | 0.0149 | 1.4352 |
| 1 | 0.25 | fast | 839 | 0.8153 | 0.0742 | 3.2182 |
| 1 | 0.5 | fast | 839 | 0.5936 | 0.073 | 3.2182 |
| 1 | 0.75 | fast | 839 | 0.4005 | 0.0693 | 3.2182 |
| 1 | 1.0 | fast | 839 | 0.2849 | 0.0872 | 3.2182 |
| 2 | 0.25 | fast | 839 | 0.1132 | -0.0475 | 3.2182 |
| 2 | 0.5 | fast | 839 | 0.0787 | -0.0378 | 3.2182 |
| 2 | 0.75 | fast | 839 | 0.0536 | -0.0337 | 3.2182 |
| 2 | 1.0 | fast | 839 | 0.0346 | -0.0326 | 3.2182 |
| 3 | 0.25 | fast | 839 | 0.1132 | -0.0064 | 3.2182 |
| 3 | 0.5 | fast | 839 | 0.1514 | -0.0037 | 3.2182 |
| 3 | 0.75 | fast | 839 | 0.1383 | 0.0158 | 3.2182 |
| 3 | 1.0 | fast | 839 | 0.1073 | 0.0065 | 3.2182 |
| 1 | 0.25 | slow | 689 | 0.7736 | 0.0624 | 0.7171 |
| 1 | 0.5 | slow | 689 | 0.5588 | 0.073 | 0.7171 |
| 1 | 0.75 | slow | 689 | 0.3962 | 0.078 | 0.7171 |
| 1 | 1.0 | slow | 689 | 0.2859 | 0.0933 | 0.7171 |
| 2 | 0.25 | slow | 689 | 0.1161 | -0.0056 | 0.7171 |
| 2 | 0.5 | slow | 689 | 0.0755 | -0.002 | 0.7171 |
| 2 | 0.75 | slow | 689 | 0.0493 | -0.0004 | 0.7171 |
| 2 | 1.0 | slow | 689 | 0.029 | -0.0135 | 0.7171 |
| 3 | 0.25 | slow | 689 | 0.1132 | 0.0317 | 0.7171 |
| 3 | 0.5 | slow | 689 | 0.1422 | 0.0116 | 0.7171 |
| 3 | 0.75 | slow | 689 | 0.148 | 0.0323 | 0.7171 |
| 3 | 1.0 | slow | 689 | 0.1074 | 0.0205 | 0.7171 |


## 8. CISD (Change in State of Delivery) Impact


### NQ1 — Play outcomes by CISD direction

| CISD Direction | Play | N | WR | Exp (R) | PF |
|---|---|---|---|---|---|
| Bullish CSD | Play 1 — IB Breakout | 81372 | 0.4655 | 0.0812 | 1.0877 |
| Bullish CSD | Play 2 — IB Retest | 81372 | 0.0893 | 0.014 | 0.6148 |
| Bullish CSD | Play 3 — IB Fade | 81372 | 0.1232 | 0.0274 | 1.086 |
| Bearish CSD | Play 1 — IB Breakout | 80072 | 0.4682 | 0.0883 | 1.1212 |
| Bearish CSD | Play 2 — IB Retest | 80072 | 0.0896 | 0.0204 | 0.6347 |
| Bearish CSD | Play 3 — IB Fade | 80072 | 0.1193 | 0.0261 | 1.0669 |
| No CSD | Play 1 — IB Breakout | 4572 | 0.6918 | 0.1871 | 1.8299 |
| No CSD | Play 2 — IB Retest | 4572 | 0.1719 | 0.003 | 0.9148 |
| No CSD | Play 3 — IB Fade | 4572 | 0.2095 | 0.0546 | 1.3486 |


### ES1: CISD fields not yet computed


### YM1: CISD fields not yet computed


### RTY1: CISD fields not yet computed


### CL1: CISD fields not yet computed


### GC1: CISD fields not yet computed


## 9. Conviction Score v2 Distribution


### NQ1

- Rows: 41504

- Mean: 0.604

- Median: 0.630

- Range: 0.000 – 0.881

- Score > 0: 38426 rows (92.6%)

- Score ≥ 0.5: 37067 rows (89.3%)

- Score ≥ 0.7: 6962 rows (16.8%)


## 10. Optimal Filter Stacks (Phase 4c — Greedy Forward Selection)

| Symbol | Target | Filter Stack | # Filters | N Trades | WR | Baseline WR | Exp (R) |
|---|---|---|---|---|---|---|---|
| NQ1 | play1_result | break_vs_avwap_0930|trend_misaligned_with_break|ib_vcp_3day_contracting|is_opex_week|ib_low_body_close | 5 | 241 | 0.4232 | 0.2885 | -0.1535 |
| NQ1 | play2_result | break_vs_avwap_0930|trend_misaligned_with_break|ib_vcp_3day_contracting|is_opex_week|break_dir_matches_avwap0930 | 5 | 219 | 0.1553 | 0.0991 | -0.2785 |
| NQ1 | play3_result | break_vs_avwap_0930|ib_vcp_3day_contracting|is_quarterly_opex|ib_high_body_close | 4 | 59 | 0.2034 | 0.1367 | 0.0508 |
| NQ1 | bias_correct_combined_05x | break_vs_avwap_0930|trend_aligned_with_break|ib_news_break | 3 | 59 | 0.5085 | 0.342 | 0.5085 |
| NQ1 | realized_dir_break | break_vs_avwap_0930|trend_misaligned_with_break|ib_high_body_close|ib_vcp_3day_contracting|is_opex_friday | 5 | 56 | 0.625 | 0.4747 | 0.25 |


## 11. Strategy Catalog Reference

See [PRD §10](../../../plans/2026-07-24-ib-data-gathering-plan.md) for the full 83-strategy catalog, 21 entry techniques, 17 stops, 20 take-profit techniques.


## 12. Methodology Notes

- **Win Rate (WR):** fraction of trades with result == 1.

- **Expectancy:** mean of `realized_r` (in R-multiples).

- **Profit Factor:** gross win R / gross loss R.

- **MFE/MAE:** max favorable / max adverse excursion in R.

- **Lift:** WR(flag on) − WR(flag off). Measured against per-symbol baseline, not naive 50%.

- **Regime:** from `ib_regime_{SYM}.parquet` (Phase 6 classifier: trend/normal/range/skip).

- **CISD:** from `ib_cisd_dir` in confluence (1=bullish CSD fired, -1=bearish, 0=none). Per the CISD document, a CSD fires when price trades through the candidate candle's open (not close-based).

- All stats are in-sample (no train/test split in this report). Phase 4's validation harness applies bootstrap CIs and min-N guards for production use.
