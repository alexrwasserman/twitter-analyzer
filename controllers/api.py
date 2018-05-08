from enum import Enum
import operator
import os
import re
import string

import boto3
import botocore
import emoji
from flask import *
from nltk.corpus import stopwords
from nltk.tokenize import TweetTokenizer
import twitter

class Analysis(Enum):
    HOMEMADE = 1

TWEETS_PER_REQUEST_LIMIT = 200

api = Blueprint('api', __name__, template_folder='templates')

@api.route('/api/v1/analyze', methods=['GET'])
def analyze():
    params = request.args

    error = check_inputs(params)
    if error:
        return error, 400

    username = params['username']
    method = params['method']

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
            raise

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

    try:
        Analysis(int(params['method']))
    except ValueError as e:
        return params['method'] + ' is not a recognized method'

    if not re.search('^(\w){1,15}$', params['username']) or re.search('Twitter|Admin', params['username']):
        return params['username'] + ' is not a valid Twitter username'


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

            preprocessed_tweet = preprocess_tweet(tweet.full_text)

            if len(preprocessed_tweet):
                for token in preprocessed_tweet:
                    f.write('"' + token + '",')

                f.write('\n')
            else:
                f.write(',\n')

    return len(tweets)


def preprocess_tweet(tweet):
    tokenizer = TweetTokenizer(preserve_case=False)
    return [token for token in tokenizer.tokenize(tweet) if token_is_allowed(token)]


def token_is_allowed(token):
    regex_patterns = [
        '^https?://',   # URL
        u'^\u2019$',    # right single quotation
        u'^\ufe0e$',    # variation selector 15
        u'^\ufe0f$'     # variation selector 16
    ]

    if token in stopwords.words('english'):
        return False
    if token in emoji.UNICODE_EMOJI:
        return False
    if token in string.punctuation:
        return False
    for pattern in regex_patterns:
        if re.search(pattern, token):
            return False

    return True
