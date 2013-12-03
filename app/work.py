from decorators import async
import logging,json
import twitter
from functools import partial
from sys import maxint
import sys
import time
from urllib2 import URLError
from httplib import BadStatusLine
#from neo4jrestclient import client
from app import app


from flask.ext.mail import Message

#def getGraph():
#	return client.GraphDatabase("http://localhost:7474/db/data/")

def oauth_login():

    CONSUMER_KEY = ''
    CONSUMER_SECRET = ''
    OAUTH_TOKEN = ''
    OAUTH_TOKEN_SECRET = ''

    auth = twitter.oauth.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET,
                               CONSUMER_KEY, CONSUMER_SECRET)

    twitter_api = twitter.Twitter(auth=auth)
    return twitter_api

def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw): 
    
    # A nested helper function that handles common HTTPErrors. Return an updated
    # value for wait_period if the problem is a 500 level error. Block until the
    # rate limit is reset if it's a rate limiting issue (429 error). Returns None
    # for 401 and 404 errors, which requires special handling by the caller.
    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):
    
        if wait_period > 3600: # Seconds
            print >> sys.stderr, 'Too many retries. Quitting.'
            raise e
    
        # See https://dev.twitter.com/docs/error-codes-responses for common codes
    
        if e.e.code == 401:
            print >> sys.stderr, 'Encountered 401 Error (Not Authorized)'
            return None
        elif e.e.code == 404:
            print >> sys.stderr, 'Encountered 404 Error (Not Found)'
            return None
        elif e.e.code == 429: 
            print >> sys.stderr, 'Encountered 429 Error (Rate Limit Exceeded)'
            if sleep_when_rate_limited:
                print >> sys.stderr, "Retrying in 15 minutes...ZzZ..."
                sys.stderr.flush()
                time.sleep(60*15 + 5)
                print >> sys.stderr, '...ZzZ...Awake now and trying again.'
                return 2
            else:
                raise e # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            print >> sys.stderr, 'Encountered %i Error. Retrying in %i seconds' % \
                (e.e.code, wait_period)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    # End of nested helper function
    
    wait_period = 2 
    error_count = 0 

    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError, e:
            error_count = 0 
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError, e:
            error_count += 1
            print >> sys.stderr, "URLError encountered. Continuing."
            if error_count > max_errors:
                print >> sys.stderr, "Too many consecutive errors...bailing out."
                raise
        except BadStatusLine, e:
            error_count += 1
            print >> sys.stderr, "BadStatusLine encountered. Continuing."
            if error_count > max_errors:
                print >> sys.stderr, "Too many consecutive errors...bailing out."
                raise

def get_friends_followers_ids(twitter_api, screen_name=None, user_id=None,
                              friends_limit=maxint, followers_limit=maxint):
    
    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None), \
    "Must have screen_name or user_id, but not both"    
    
    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids, 
                              count=5000)
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids, 
                                count=5000)

    friends_ids, followers_ids = [], []
    
    for twitter_api_func, limit, ids, label in [
                    [get_friends_ids, friends_limit, friends_ids, "friends"], 
                    [get_followers_ids, followers_limit, followers_ids, "followers"]
                ]:
        
        if limit == 0: continue
        
        cursor = -1
        while cursor != 0:
        
            # Use make_twitter_request via the partially bound callable...
            if screen_name: 
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else: # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']
        
            print >> sys.stderr, 'Fetched {0} total {1} ids for {2}'.format(len(ids), 
                                                    label, (user_id or screen_name))
                
            if len(ids) >= limit or response is None:
                break

    return friends_ids[:friends_limit], followers_ids[:followers_limit] 


def fill_graph(gdb,userId,users,type):
		if(not gdb is None):
	                print >> sys.stderr, 'gdb is not none'
		else:
	                print >> sys.stderr, 'gdb is none: exit'
			return
		user = None
		q = 'START n=node(*) WHERE (has(n.userId) and (n.userId = '+str(userId)+')) RETURN n'
                result = gdb.query(q, returns=(client.Node))
		user = result[0][0] if len(result) == 1 else gdb.node(userId=userId)
		
		print >> sys.stderr, 'updating graph in fill_graph function, type: {0}, for user: {1}'.format(type,userId)
	
		for u in users:
			q = 'START n=node(*) WHERE (has(n.userId) and (n.userId = '+str(u)+')) RETURN n'
			result = gdb.query(q, returns=(client.Node))
			ux = result[0][0] if len(result)==1 else gdb.node(userId=u)	
			ux.follows(user) if type == "followers" else user.follows(ux)
	
def update_graph_job(screen_name):
	update_graph(screen_name)
	
def lookup_twitter_user(screen_name):
	try:
		api = oauth_login()
		user_id = api.users.lookup(screen_name=screen_name)[0]['id']
		return True,user_id
	except twitter.TwitterHTTPError,te:
		return False,screen_name
	except Exception:
		return False,screen_name	
	
def create_csv(userId,users):
	me = str(userId)
	with open("data-"+str(userId)+".csv","w") as input:
				input.write("source,target,type\n")	
	with open("data-"+str(userId)+".csv","a") as input1:
			input1.write("".join(str(follower)+','+me+',follows\n' for follower in users))
def create_csv2(userId,users):
	me = str(userId)
	with open("data-"+str(userId)+".csv","a") as input2:
			input2.write("".join(me+','+str(friend)+',friend\n' for friend in users))
@async
def update_graph(user_id):
	try:
		api = oauth_login()
		friends_ids, followers_ids = get_friends_followers_ids(api,user_id=user_id)
		#print >> sys.stderr, 'updating graph for user id: {0} (friends)'.format(user_id) 	
		#fill_graph(getGraph(),user_id,friends_ids, "friends")
		#print >> sys.stderr, 'updating graph for user id: {0} (followers)'.format(user_id)
		#fill_graph(getGraph(),user_id,followers_ids, "followers")
		print >> sys.stderr, 'create csv for user id: {0} (followers)'.format(user_id)
		create_csv(user_id,followers_ids) #followers
		print >> sys.stderr, 'create csv for user id: {0} (friends)'.format(user_id)
		create_csv2(user_id,friends_ids) #friends
		print >> sys.stderr, 'sending mail complete {0} (friends)'.format(user_id)
	except Exception,e:
		print >> sys.stderr, 'Exception: {0}'.format(e)
