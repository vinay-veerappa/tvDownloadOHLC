# IB Strategy Statistics — Comprehensive Report

**Generated:** 2026-07-25  
**Symbols:** NQ1


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
