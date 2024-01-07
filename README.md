# BTC-price-fetcher
Key features
- Uses Amazon Cognito to handle authentication.
- Aurora PostgreSQL as DB backend 
- CoinGecko API to fetch current prices
### Breakdown components and functionalities:
1. Configuration and Initialization:
- The app configures AWS Cognito for user authentication.
- Database configuration is set up using SQLAlchemy.
- I used Aurora PostgreSQL to set up scalable DB.
2. Database Model (BtcPrice):
-  Defines a model for storing Bitcoin prices with fields for EUR and CZK prices and a
timestamp.
3. Fetching and Storing Bitcoin Prices:
-  The `fetch_btc_price` function calls the CoinGecko API to get the current Bitcoin prices
in EUR and CZK. 5 minute intervals should be far enough apart to use free API
indefinitely. CoinGecko free API has a rate limit of 10-30 calls/minute and 10000 calls
per month.
- The `store_btc_price` function stores these prices in the database.
4. Scheduler for Regular Updates:
- A background scheduler is set up to run the store_btc_price function every 5
minutes. This amounts to approximately 8640 calls/month.
5. Endpoints:
- `GET /get_btc_price`: Fetches and returns the current Bitcoin price, also storing this
data in the database. Requires Cognito authentication. Expects Bearer token.
- 1. Sample response:
`{"btc_prices":{"czk":{"currency":"CZK","price_per_btc":993625},
"eur":{"currency":"EUR","price_per_btc":40320}},"client_request
_time":"2024-01-07T19:30:59.176913+00:00"}`
- `GET /get_averages`: Calculates and returns current day and current month average
prices of Bitcoin. Requires Cognito authentication. Expects Bearer token.
- 1. Sample response:
`{"daily_average":{"CZK":991167.25,"EUR":40184.25},"monthly_aver
age":{"CZK":991167.25,"EUR":40184.25},"server_data_time":"2024-
01-07T17:32:59.837272+00:00"}`
- `/callback`: A utility endpoint, for OAuth2 callbacks. Currently not necessary
- `POST /get_token`: Authenticates client with AWS Cognito and returns an ID token.
Expects username and password in JSON format.
- 1. `{"username": "<username>", "password": "<password>"}`
6. Helper Functions:
- `calculate_daily_average` and `calculate_monthly_average` compute the average
Bitcoin prices for the current day and month, respectively.
7. AWS Cognito Authentication:
- Uses AWS Cognito for user authentication, with routes protected by the
`cognito_auth_required` decorator.
o Handles user token generation and validation.
8. Execution:
- The application is set to run on localhost port 5000 in debug mode.

### TODO
At this point the microservice is in no way production ready. Some of the most important
functionalities to consider:
- Use HTTPS – This is the most important. Right now, the app expects username and password
JSON formatted sent using http.
- Input Validation – to prevent common attacks.
- Error Handling and Logging
- Caching and DB access optimizations 
  - It would make sense to store current and calculated averages in memory until they
  become stale (maybe at scheduler interval?). Right now, external API is called on
  every call of `/get_btc_price` endpoint. This would eventually incur unnecessary
  costs and needlessly slow the execution. Caching would solve this problem.
  - Currently, if multiple instances of the app are deployed, they will all store data in 5-
  minute intervals. While still in line with datapoints being at most 5 minutes apart, it
  wouldn't make much sense for higher number of replicas. This could be solved by
  implementing check for latest stored datapoint or by splitting the service in two
  parts, one for string the data and one to answer client request.
- API rate limiting – There is no benefit for client app to frequently query endpoints which are
updated in regular intervals. Rate limiting would prevent abuse.
- Data retention - I’ve not implemented data retention. Storing data at 5-minute intervals
amounts to roughly 160MB per year which is not particularly high. If data retention must be
implemented then, given current DB implementation, table partitioning by year/year&month
can be implemented to optimize record deletion.
- Additional / Improved authentication - ditch username and password for cleaner alternative, implement Hashicorp Vault and use dynamic secrets, use MFA, ...
### Docker file
This Dockerfile, sets up a container using Python 3.9.5. It installs necessary dependencies, copies the application files into the
container, and configures Gunicorn to serve the app on port 5000. The setup includes lib installation
for PostgreSQL support (psycopg2) and is designed for efficient deployment and running of the Python
application.
### Helm
Helm chart defines a Kubernetes Deployment for the `btc-price-app`. It configures
one instance of the app with specific environment variables and deploys it using a Docker image. The
application is exposed on port 5000.
To deploy this application using Helm, use

`helm install btc-price-app btc-price-app-helm --namespace btc-app --createnamespace`

This command installs the Helm chart named `btc-price-app-helm` as `btc-price-app` in the
Kubernetes namespace `btc-app`. The `--create-namespace` flag ensures that the namespace is
created if it doesn't already exist.