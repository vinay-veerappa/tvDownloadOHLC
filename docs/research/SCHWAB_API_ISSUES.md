# Schwab API Diagnostics (Dec 17, 2025)

## 1. Issue Description
The Schwab API setup is currently in a "Market Data Only" state. 
- **Working**: `/marketdata/v1/quotes` (and Expected Move logic).
- **Broken**: `/trader/v1/accounts`, `/trader/v1/userPreference` (Streaming Login).

## 2. Root Cause Analysis
The API gateway returns the following error for any Trader API call:
`error_description="keymanagement.service.InvalidAPICallAsNoApiProductMatchFound: Invalid API call as no apiproduct match found"`

This means the **Consumer Key** (active in `secrets.json`) is not associated with the **Trader API Product** in the Schwab Developer Portal.

## 3. Findings from Reddit Guide
- **Account Hashing**: Once authorized, account-specific requests MUST use the `hashValue` from `/accounts/accountNumbers`.
- **Headers**: Some endpoints may require `accept: */*` and `Content-Type: application/json`.
- **Verification**: In our tests, adding these headers changed the 401 to a 400/500, but the "No Product Match" error persisted in the WWW-Authenticate header.

## 4. Required Action
1.  **Verify App Products**: Ensure the App in the portal has **BOTH** "Market Data" and "Trader API" listed under Products.
2.  **Regenerate Key**: If "Trader API" was added recently, the key might need to be regenerated or a new app created.
3.  **Wait for Approval**: Access to the Trader API sometimes requires manual approval by Schwab, even if Market Data is instant.
