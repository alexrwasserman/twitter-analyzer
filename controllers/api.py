import os
import re
import operator

import boto3
import botocore
import twitter
from flask import *

PERMITTED_ANALYSES = [
    'homemade'
]
TWEETS_PER_REQUEST_LIMIT = 200

api = Blueprint('api', __name__, template_folder='templates')

@api.route('/api/v1/analyze', methods=['GET'])
def analyze():
    params = request.args

    error = check_inputs(params)
    if error:
        return error

    username = params['username']
    method = params['method']

    create_tweets_dir()

    s3 = boto3.Session(
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY']
    ).resource('s3')

    bucket_name = 'ta-cached-tweets'
    s3_key = username + '-tweets.txt'
    local_filename = 'tweets/' + s3_key

    try:
        s3.Bucket(bucket_name).download_file(s3_key, local_filename)
        user_has_cached_tweets = True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            user_has_cached_tweets = False
        else:
            error = str(e)
    except Exception as e:
        error = str(e)

    if error:
        return error

    new_tweets = update_tweets_file(username, local_filename, user_has_cached_tweets)

    if new_tweets:
        s3.meta.client.upload_file(local_filename, bucket_name, s3_key)

    # TODO: this is where the analysis should be done

    return 'done'


def check_inputs(params):
    if 'username' not in params and 'method' in params:
        return 'Missing the required "username" parameter'
    elif 'method' not in params and 'username' in params:
        return 'Missing the requried "method" parameter'
    elif 'username' not in params and 'method' not in params:
        return 'Missing the required "username" and "method" parameters'

    if params['method'] not in PERMITTED_ANALYSES:
        return params['method'] + ' is not a recognized method'

    if not re.search('^(\w){1,15}$', params['username']) or re.search('Twitter|Admin', params['username']):
        return params['username'] + ' is not a valid Twitter username'


# Each tweet in tweets file will be of the format:
# id
# created at (seconds since epoch)
# tokenized text
def update_tweets_file(username, filename, user_has_cached_tweets):
    api = twitter.Api(
        consumer_key=os.environ['TWITTER_CONSUMER_KEY'],
        consumer_secret=os.environ['TWITTER_CONSUMER_SECRET'],
        access_token_key=os.environ['TWITTER_ACCESS_TOKEN'],
        access_token_secret=os.environ['TWITTER_ACCESS_TOKEN_SECRET'],
        tweet_mode='extended',
        sleep_on_rate_limit=True
    )

    if user_has_cached_tweets:
        with open(filename, 'r') as f:
            last_cached_tweet = int(f.readlines()[-3])
    else:
        last_cached_tweet = None

    tweets = []

    # Get most recent tweets
    newest_batch = api.GetUserTimeline(
        screen_name=username,
        count=TWEETS_PER_REQUEST_LIMIT,
        trim_user=True,
        since_id=last_cached_tweet
    )
    tweets = tweets + newest_batch

    while len(newest_batch) == TWEETS_PER_REQUEST_LIMIT:
        # user most likely has more tweets to fetch
        oldest_fetched_tweet = sorted(newest_batch, key=operator.attrgetter('created_at_in_seconds'))[0].id
        newest_batch = api.GetUserTimeline(
            screen_name=username,
            count=TWEETS_PER_REQUEST_LIMIT,
            trim_user=True,
            since_id=last_cached_tweet,
            max_id=oldest_fetched_tweet
        )

        # Must delete duplicate tweet whose id == oldest_tweet_fetched
        tweets = tweets + [tweet for tweet in newest_batch if tweet.id != oldest_fetched_tweet]

    tweets.sort(key=operator.attrgetter('created_at_in_seconds'))

    with open(filename, 'a') as f:
        for tweet in tweets:
            f.write(str(tweet.id) + '\n')
            f.write(str(tweet.created_at_in_seconds) + '\n')
            # TODO: preprocess and tokenize text
            f.write(tweet.full_text.replace('\n', ' ') + '\n')

    return len(tweets)


def create_tweets_dir():
    if not os.path.exists('tweets'):
        os.makedirs('tweets')
