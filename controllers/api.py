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

    s3 = boto3.Session(
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY']
    ).resource('s3')

    bucket_name = 'ta-cached-tweets'
    filename = username + '-tweets.txt'
    must_create_file = False

    try:
        s3.Bucket(bucket_name).download_file(filename, filename)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            must_create_file = True
        else:
            error = str(e)
    except Exception as e:
        error = str(e)

    if error:
        return error

    update_tweets_file(username, filename, must_create_file)

    # TODO: this is where the analysis should be done

    s3.meta.client.upload_file(filename, bucket_name, filename)

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
def update_tweets_file(username, filename, must_create_file):
    # TODO: Decide if sleeping once the limit is reached is the desired behavior
    api = twitter.Api(
        consumer_key=os.environ['TWITTER_CONSUMER_KEY'],
        consumer_secret=os.environ['TWITTER_CONSUMER_SECRET'],
        access_token_key=os.environ['TWITTER_ACCESS_TOKEN'],
        access_token_secret=os.environ['TWITTER_ACCESS_TOKEN_SECRET'],
        tweet_mode='extended',
        sleep_on_rate_limit=True
    )

    if must_create_file:
        create_new_tweets_file(api, username, filename)
    else:
        add_recents_to_tweets_file(api, username, filename)


def create_new_tweets_file(api, username, filename):
    tweets = []

    # Get 200 most recent tweets
    newest_batch = api.GetUserTimeline(
        screen_name=username,
        count=TWEETS_PER_REQUEST_LIMIT,
        trim_user=True
    )
    tweets = tweets + newest_batch

    while len(newest_batch) == TWEETS_PER_REQUEST_LIMIT:
        # user most likely has more tweets to fetch
        oldest_id = sorted(newest_batch, key=operator.attrgetter('created_at_in_seconds'))[0].id
        newest_batch = api.GetUserTimeline(
            screen_name=username,
            count=TWEETS_PER_REQUEST_LIMIT,
            trim_user=True,
            max_id=oldest_id)
        tweets = tweets + newest_batch

    tweets.sort(key=operator.attrgetter('created_at_in_seconds'), reverse=True)

    with open(filename, 'w') as f:
        for tweet in tweets:
            f.write(str(tweet.id) + '\n')
            f.write(str(tweet.created_at_in_seconds) + '\n')
            # TODO: preprocess and tokenize text
            f.write(tweet.full_text + '\n')


def add_recents_to_tweets_file(api, username, filename):
    pass
