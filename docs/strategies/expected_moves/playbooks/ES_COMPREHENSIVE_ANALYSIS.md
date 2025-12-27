# ES Futures: Comprehensive Expected Move Analysis

This document details the performance of Expected Move (EM) levels specifically for **ES Futures**, based on extrapolated settlement data and aligned trading sessions.

## 1. Executive Summary

**Top Performing Method (1.0x / 100% EM):** straddle_100_close
- Close Containment: **100.0%**
- Intraday Touch Rate: **4.5%**
- S/R Bounce Rate: **100.0%** (Probability of holding when tested)

---

## 2. Intraday S/R Analysis (Bounce vs. Break)

This metric answers: *"If the level is hit intraday, how likely is it to hold by the close?"*

| Method | Multiple | Touch Rate | Bounce Rate (Hold) | Break Rate (Fail) |
| :--- | :--- | :--- | :--- | :--- |
| straddle_100_close | 1.0x | 4.5% | **100.0%** | 0.0% |
| straddle_085_close | 1.0x | 13.0% | **88.5%** | 11.5% |
| straddle_085_open | 1.0x | 1.5% | **66.7%** | 33.3% |
| synth_vix_100_open | 1.0x | 2.3% | **36.4%** | 63.6% |
| vix_scaled_close | 1.0x | 33.2% | **34.0%** | 66.0% |
| synth_vix_085_open | 1.0x | 3.1% | **33.3%** | 66.7% |
| straddle_100_open | 1.0x | 0.8% | **33.3%** | 66.7% |
| iv365_close | 1.0x | 76.3% | **32.3%** | 67.7% |
| iv252_close | 1.0x | 68.1% | **29.0%** | 71.0% |
| vix_raw_close | 1.0x | 65.3% | **28.9%** | 71.1% |

> **Trading Insight**: A high Bounce Rate (>60%) suggests the level acts as valid Support/Resistance for fading. A low Bounce Rate (<40%) suggests the level is a breakout trigger.

---

## 3. Overnight Session Analysis

Overnight containment of Previous Daily Close Levels:

| Session | Anchor | Multiple | Containment % | Touch Upper % | Touch Lower % | Median MFE | Median MAE | Samples |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| overnight | prev_close | 0.5 | 33.88% | 63.66% | 4.1% | 0.1482 | 0.1276 | 366 |
| overnight | prev_close | 1.0 | 95.63% | 4.1% | 0.27% | 0.1482 | 0.1276 | 366 |
| overnight | prev_open | 0.5 | 29.23% | 63.93% | 7.65% | 0.1482 | 0.1276 | 366 |
| overnight | prev_open | 1.0 | 83.61% | 15.03% | 1.37% | 0.1482 | 0.1276 | 366 |


## 4. Full Performance Data

| Method | Multiple | Containment (Close) | Median MFE | Median MAE |
| :--- | :--- | :--- | :--- | :--- |
| straddle_100_open | 0.5 | 94.7% | 0.150 | 0.158 |
| straddle_085_open | 0.5 | 92.0% | 0.176 | 0.186 |
| synth_vix_100_open | 0.5 | 91.4% | 0.181 | 0.181 |
| synth_vix_085_open | 0.5 | 88.5% | 0.213 | 0.213 |
| straddle_100_close | 0.5 | 73.9% | 0.515 | -0.115 |
| straddle_085_close | 0.5 | 60.4% | 0.606 | -0.135 |
| vix_scaled_close | 0.5 | 53.2% | 0.709 | -0.239 |
| iv252_close | 0.5 | 35.9% | 1.430 | -0.307 |
| vix_raw_close | 0.5 | 34.0% | 1.418 | -0.479 |
| iv365_close | 0.5 | 32.2% | 1.721 | -0.369 |
| straddle_100_open | 0.618 | 97.2% | 0.150 | 0.158 |
| straddle_085_open | 0.618 | 96.2% | 0.176 | 0.186 |
| synth_vix_100_open | 0.618 | 95.4% | 0.181 | 0.181 |
| synth_vix_085_open | 0.618 | 91.6% | 0.213 | 0.213 |
| straddle_100_close | 0.618 | 83.2% | 0.515 | -0.115 |
| straddle_085_close | 0.618 | 76.7% | 0.606 | -0.135 |
| vix_scaled_close | 0.618 | 58.7% | 0.709 | -0.239 |
| iv252_close | 0.618 | 42.1% | 1.430 | -0.307 |
| vix_raw_close | 0.618 | 38.2% | 1.418 | -0.479 |
| iv365_close | 0.618 | 36.2% | 1.721 | -0.369 |
| straddle_100_close | 1.0 | 100.0% | 0.515 | -0.115 |
| straddle_085_open | 1.0 | 99.5% | 0.176 | 0.186 |
| straddle_100_open | 1.0 | 99.5% | 0.150 | 0.158 |
| synth_vix_100_open | 1.0 | 98.5% | 0.181 | 0.181 |
| straddle_085_close | 1.0 | 98.5% | 0.606 | -0.135 |
| synth_vix_085_open | 1.0 | 97.9% | 0.213 | 0.213 |
| vix_scaled_close | 1.0 | 78.1% | 0.709 | -0.239 |
| vix_raw_close | 1.0 | 53.2% | 1.418 | -0.479 |
| iv252_close | 1.0 | 51.1% | 1.430 | -0.307 |
| iv365_close | 1.0 | 47.1% | 1.721 | -0.369 |
| straddle_085_close | 1.272 | 100.0% | 0.606 | -0.135 |
| straddle_100_close | 1.272 | 100.0% | 0.515 | -0.115 |
| straddle_085_open | 1.272 | 99.7% | 0.176 | 0.186 |
| straddle_100_open | 1.272 | 99.7% | 0.150 | 0.158 |
| synth_vix_100_open | 1.272 | 99.4% | 0.181 | 0.181 |
| synth_vix_085_open | 1.272 | 99.0% | 0.213 | 0.213 |
| vix_scaled_close | 1.272 | 94.2% | 0.709 | -0.239 |
| iv252_close | 1.272 | 63.1% | 1.430 | -0.307 |
| vix_raw_close | 1.272 | 60.3% | 1.418 | -0.479 |
| iv365_close | 1.272 | 53.6% | 1.721 | -0.369 |
| vix_scaled_close | 1.5 | 100.0% | 0.709 | -0.239 |
| straddle_085_close | 1.5 | 100.0% | 0.606 | -0.135 |
| straddle_100_close | 1.5 | 100.0% | 0.515 | -0.115 |
| synth_vix_100_open | 1.5 | 99.8% | 0.181 | 0.181 |
| straddle_085_open | 1.5 | 99.7% | 0.176 | 0.186 |
| straddle_100_open | 1.5 | 99.7% | 0.150 | 0.158 |
| synth_vix_085_open | 1.5 | 99.4% | 0.213 | 0.213 |
| vix_raw_close | 1.5 | 68.3% | 1.418 | -0.479 |
| iv252_close | 1.5 | 67.3% | 1.430 | -0.307 |
| iv365_close | 1.5 | 62.8% | 1.721 | -0.369 |
| vix_scaled_close | 1.618 | 100.0% | 0.709 | -0.239 |
| straddle_085_close | 1.618 | 100.0% | 0.606 | -0.135 |
| straddle_100_close | 1.618 | 100.0% | 0.515 | -0.115 |
| synth_vix_100_open | 1.618 | 99.8% | 0.181 | 0.181 |
| straddle_085_open | 1.618 | 99.7% | 0.176 | 0.186 |
| straddle_100_open | 1.618 | 99.7% | 0.150 | 0.158 |
| synth_vix_085_open | 1.618 | 99.6% | 0.213 | 0.213 |
| vix_raw_close | 1.618 | 71.0% | 1.418 | -0.479 |
| iv252_close | 1.618 | 70.3% | 1.430 | -0.307 |
| iv365_close | 1.618 | 65.1% | 1.721 | -0.369 |
| vix_scaled_close | 2.0 | 100.0% | 0.709 | -0.239 |
| synth_vix_100_open | 2.0 | 100.0% | 0.181 | 0.181 |
| straddle_085_close | 2.0 | 100.0% | 0.606 | -0.135 |
| straddle_100_close | 2.0 | 100.0% | 0.515 | -0.115 |
| straddle_085_open | 2.0 | 100.0% | 0.176 | 0.186 |
| straddle_100_open | 2.0 | 100.0% | 0.150 | 0.158 |
| synth_vix_085_open | 2.0 | 99.8% | 0.213 | 0.213 |
| iv252_close | 2.0 | 80.5% | 1.430 | -0.307 |
| vix_raw_close | 2.0 | 78.1% | 1.418 | -0.479 |
| iv365_close | 2.0 | 71.8% | 1.721 | -0.369 |
