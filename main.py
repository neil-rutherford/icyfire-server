import requests
import json
from datetime import datetime
import os
import pandas as pd
import time
import dropbox
import facebook
import twitter
import tweepy
import pytumblr
import praw
import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv('.env')

server_id = os.environ['SERVER_ID']
read_token = os.environ['READ_TOKEN']
cred_token = os.environ['CRED_TOKEN']
delete_token = os.environ['DELETE_TOKEN']
secret_key = os.environ['SECRET_KEY']
salt = os.environ['SALT']
dropbox_access_key = os.environ['DROPBOX_ACCESS_KEY']


def calculate_min(server_id):
    '''
    Uses server_id variable to calculate the lower bound of its timeslots.

    :param server_id:   The server ID, as an integer.
    :return:            The lower bound timeslot ID.
    :rtype:             Integer
    :onerror:           No error handling.

    Example usage: calculate_min(server_id=5) would return int(40321).
    '''
    multiplier = int(server_id) - 1
    return (10080 * multiplier) + 1


def calculate_max(server_id):
    '''
    Uses server_id variable to calculate the upper bound of its timeslots.

    :param server_id:   The server ID, as an integer.
    :return:            The upper bound timeslot ID.
    :rtype:             Integer
    :onerror:           No error handling.

    Example usage: calculate_max(server_id=5) would return int(50400).
    '''
    multiplier = int(server_id)
    return (10080 * multiplier)


def create_dataframe(min, max):
    '''
    Iterates through all possible timeslots in a week, then creates a reference table with columns "Day of week", "Time", and "Timeslot ID".

    :param min:     The lower bound of the server's timeslots, as an integer.
    :param max:     The upper bound of the server's timeslots, as an integer.
    :return:        10080 x 3 reference table
    :rtype:         Pandas dataframe
    :onerror:       No error handling.

    Example usage: create_dataframe(min=40321, max=50400) would return a dataframe of labeled timeslots for Server #5.
    '''
    Timeslot = []
    Day_of_Week = []
    Time = []
    for x in range(min, max + 1):
        Timeslot.append(x)
    days_of_week = ['1', '2', '3', '4', '5', '6', '7']
    for z in range(0, len(days_of_week)):
        x = 0
        y = 0
        while x < 24:
            if x < 10 and y < 10:
                Time.append('0{}:0{}'.format(x,y))
                Day_of_Week.append(int(days_of_week[z]))
            elif x < 10:
                Time.append('0{}:{}'.format(x,y))
                Day_of_Week.append(int(days_of_week[z]))
            elif y < 10:
                Time.append('{}:0{}'.format(x,y))
                Day_of_Week.append(int(days_of_week[z]))
            else:
                Time.append('{}:{}'.format(x,y))
                Day_of_Week.append(int(days_of_week[z]))
            y += 1
            if y > 59:
                y = 0
                x += 1
    assert len(Timeslot) == len(Day_of_Week) == len(Time), 'Lengths are not the same'
    data = {'Timeslot': Timeslot, 'Day_of_Week': Day_of_Week, 'Time': Time}
    df = pd.DataFrame(data, columns=['Timeslot', 'Day_of_Week', 'Time'])
    return df


def current_slot(df):
    '''
    Uses the UTC time now to determine which timeslot ID to start at.

    :param df:      A Pandas dataframe object generated by calling the `create_dataframe` function.
    :return:        The appropriate timeslot ID.
    :rtype:         Integer
    :onerror:       No error handling.

    Example usage: current_slot(df=create_dataframe(1, 10800)) run at 0:00 Monday UTC would return int(1).
    '''
    day_of_week = int(datetime.utcnow().strftime('%w'))
    if day_of_week == 0:
        day_of_week = 7
    time = datetime.utcnow().strftime('%H:%M')
    return int(df[(df.Day_of_Week == day_of_week) & (df.Time == time)].iloc[0]['Timeslot'])


def decrypt(message):
    '''
    Decrypts social media creds that are sent over by the IcyFire API.

    :param message:     The encrypted string.
    :return:            The decrypted string.
    :rtype:             String
    :onerror:           No error handling.

    Example usage: decrypt('G4rbl3dYg00k') would return str('plaintext').
    '''
    password_provided = os.environ['SECRET_KEY']
    password = password_provided.encode()
    salt = os.environ['SALT'].encode()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000, backend=default_backend())
    key = base64.urlsafe_b64encode(kdf.derive(password))
    message = message.encode()
    f = Fernet(key)
    decrypted = f.decrypt(message)
    return decrypted.decode()


def download_multimedia(multimedia_url):
    '''
    If a file doesn't already exist in the directory, this function downloads it from Dropbox and saves it in the "multimedia" folder.

    :param file_name:   The file name and extension, as a string.
    :return:            Creation of file object
    :onerror:           Prints error as a string.

    Example usage: download_multimedia('example.jpg') would connect to "Dropbox/multimedia/example.jpg", then download the file locally to "./multimedia/example.jpg".
    '''
    file_name = str(multimedia_url).split('/')[-1:]
    if not os.path.exists('./multimedia/{}'.format(file_name)):
        try:
            dbx = dropbox.Dropbox(os.environ['DROPBOX_ACCESS_KEY'])
            with open(f"./multimedia/{file_name}", 'wb') as f:
                metadata, res = dbx.files_download(path='/multimedia/{}'.format(file_name))
                f.write(res.content)
        except Exception as e:
            print('Download multimedia error: {}'.format(str(e)))


def delete_multimedia(multimedia_url):
    '''
    If the file exists, this function deletes it locally and from Dropbox.

    :param file_name:   The file name and extension, as a string.
    :return:            Deletion of file object
    :onerror:           Prints error as a string.

    Example usage: delete_multimedia('example.jpg') would delete "Dropbox/multimedia/example.jpg" as well as the local file stored at "./multimedia/example.jpg".
    '''
    file_name = str(multimedia_url).split('/')[-1:]
    if os.path.exists('./multimedia/{}'.format(file_name)):
        os.remove('./multimedia/{}'.format(file_name))
    try:
        dbx = dropbox.Dropbox(os.environ['DROPBOX_ACCESS_KEY'])
        dbx.files_delete_v2(path='/multimedia/{}'.format(file_name))
    except Exception as e:
        print("Delete multimedia error: {}".format(str(e)))


def facebook_short_text(access_token, page_id, body, link_url, tags):
    '''
    Publishes a short text post to Facebook, then deletes it from the queue.

    :param access_token:    The account's decrypted access token, as a string.
    :param page_id:         The name of the target page, as a string.
    :param body:            The post body, as a string.
    :param link_url:        The link URL, as a string.
    :param tags:            Preprocessed tags, as a string.
    :return:                A Facebook submission object.
    :onerror:               Prints the status code.
    '''
    fb = requests.post(f'https://graph.facebook.com/{page_id}/feed?message={body + link_url + tags}&access_token={access_token}')
    if fb.status_code == 200:
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    else:
        print('     Facebook short text status code: {}'.format(fb.status_code))


def facebook_long_text(access_token, page_id, body, link_url, tags):
    '''
    Publishes a long text post to Facebook, then deletes it from the queue.

    :param access_token:    The account's decrypted access token, as a string.
    :param page_id:         The name of the target page, as a string.
    :param body:            The post body, as a string.
    :param link_url:        The link URL, as a string.
    :param tags:            Preprocessed tags, as a string.
    :return:                A Facebook submission object.
    :onerror:               Prints the status code.
    '''
    fb = requests.post(f'https://graph.facebook.com/{page_id}/feed?message={body + link_url + tags}&access_token={access_token}')
    if fb.status_code == 200:
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    else:
        print('     Facebook long text status code: {}'.format(fb.status_code))


def facebook_image(access_token, page_id, caption, tags, file_name):
    '''
    Publishes an image post to Facebook, then deletes it from the queue.

    :param access_token:    The account's decrypted access token, as a string.
    :param page_id:         The name of the target page, as a string.
    :param caption:         The post body, as a string.
    :param tags:            Preprocessed tags, as a string.
    :param file_name:       The name of the local image file to be uploaded, as a string.
    :return:                A Facebook submission object.
    :onerror:               Prints the status code.
    '''
    fb = requests.post(f'https://graph.facebook.com/{page_id}/photos?url={file_name}&access_token={access_token}')
    if fb.status_code == 200:
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    else:
        print('     Facebook image status code: {}'.format(fb.status_code))


def facebook_video(access_token, page_id, caption, tags, file_name):
    '''
    Publishes a video post to Facebook, then deletes it from the queue. (Note: `publish_video` permission is required for this functionality.)

    :param access_token:    The account's decrypted access token, as a string.
    :param page_id:         The name of the target page, as a string.
    :param caption:         The post body, as a string.
    :param tags:            Preprocessed tags, as a string.
    :param file_name:       The name of the local video file to be uploaded, as a string.
    :return:                A Facebook submission object.
    :onerror:               Prints the status code.
    '''
    fb = requests.post(f'https://graph.facebook.com/{page_id}/videos?url={file_name}&access_token={access_token}')
    if fb.status_code == 200:
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    else:
        print('     Facebook video status code: {}'.format(fb.status_code))


def twitter_short_text(consumer_key, consumer_secret, access_token_key, access_token_secret, body, link_url, tags):
    '''
    Publishes a short text post to Twitter, then deletes it from the queue.

    :param consumer_key:            The account's decrypted consumer key, as a string.
    :param consumer_secret:         The account's decrypted consumer secret, as a string.
    :param access_token_key:        The account's decrypted access token key, as a string.
    :param access_token_secret:     The account's decrypted access token secret, as a string.
    :param body:                    The post body, as a string.
    :param link_url:                The link URL, as a string.
    :param tags:                    Preprocessed hashtags, as a string.
    :return:                        A Twitter submission object
    :onerror:                       Prints error as a string.
    '''
    try:
        api = twitter.Api(consumer_key=consumer_key, consumer_secret=consumer_secret, access_token_key=access_token_key, access_token_secret=access_token_secret)
        api.PostUpdate(body + '\n' + link_url + '\n' + tags)
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print("     Twitter short text error: {}".format(str(e)))


def twitter_image(consumer_key, consumer_secret, access_token_key, access_token_secret, file_name, caption, tags, link_url):
    '''
    Publishes an image post to Twitter, then deletes it from the queue.

    :param consumer_key:            The account's decrypted consumer key, as a string.
    :param consumer_secret:         The account's decrypted consumer secret, as a string.
    :param access_token_key:        The account's decrypted access token key, as a string.
    :param access_token_secret:     The account's decrypted access token secret, as a string.
    :param file_name:               The name of the local image file to be uploaded, as a string.
    :param caption:                 The post body, as a string.
    :param tags:                    Preprocessed hashtags, as a string.
    :return:                        A Twitter submission object
    :onerror:                       Prints error as a string.
    '''
    try:    
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token_key, access_token_secret)
        api = tweepy.API(auth)
        media = api.media_upload('./multimedia/{}'.format(file_name))
        tweet = caption + '\n' + link_url + '\n' + tags
        post = api.update_status(status=tweet, media_ids=[media.media_id])
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print("     Twitter image error: {}".format(str(e)))


def twitter_video(consumer_key, consumer_secret, access_token_key, access_token_secret, file_name, caption, tags):
    '''
    Publishes a video post to Twitter, then deletes it from the queue.

    :param consumer_key:            The account's decrypted consumer key, as a string.
    :param consumer_secret:         The account's decrypted consumer secret, as a string.
    :param access_token_key:        The account's decrypted access token key, as a string.
    :param access_token_secret:     The account's decrypted access token secret, as a string.
    :param file_name:               The name of the local video file to be uploaded, as a string.
    :param caption:                 The post body, as a string.
    :param tags:                    Preprocessed hashtags, as a string.
    :return:                        A Twitter submission object
    :onerror:                       Prints error as a string.
    '''
    try:
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token_key, access_token_secret)
        api = tweepy.API(auth)
        media = api.media_upload('./multimedia/{}'.format(file_name))
        tweet = caption + '\n' + link_url + '\n' + tags
        post = api.update_status(status=tweet, media_ids=[media.media_id])
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print("     Twitter video error: {}".format(str(e)))


def tumblr_short_text(consumer_key, consumer_secret, oauth_token, oauth_secret, blog_name, title, body, link_url, tags):
    '''
    Publishes a short text post to Tumblr, then deletes it from the queue.

    :param consumer_key:        The account's decrypted consumer key, as a string.
    :param consumer_secret:     The account's decrypted consumer secret, as a string.
    :param oauth_token:         The account's decrypted OAuth token, as a string.
    :param oauth_secret:        The account's decrypted OAuth secret, as a string.
    :param blog_name:           The blog name associated with the cred, as a string.
    :param title:               The post title, as a string.
    :param body:                The post body, as a string.
    :param link_url:            The link URL, as a string.
    :param tags:                Preprocessed tags, as a list object.
    :return:                    A Tumblr submission object
    :onerror:                   Prints error as a string.
    '''

    try:
        client = pytumblr.TumblrRestClient(consumer_key, consumer_secret, oauth_token, oauth_secret)
        client.create_text(blog_name, state="published", title=title, body=body + '\n' + link_url, tags=tags)
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print("     Tumblr short text error: {}".format(str(e)))
    

def tumblr_long_text(consumer_key, consumer_secret, oauth_token, oauth_secret, blog_name, title, body, link_url, tags):
    '''
    Publishes a long text post to Tumblr, then deletes it from the queue.

    :param consumer_key:        The account's decrypted consumer key, as a string.
    :param consumer_secret:     The account's decrypted consumer secret, as a string.
    :param oauth_token:         The account's decrypted OAuth token, as a string.
    :param oauth_secret:        The account's decrypted OAuth secret, as a string.
    :param blog_name:           The blog name associated with the cred, as a string.
    :param title:               The post title, as a string.
    :param body:                The post body, as a string.
    :param link_url:            The link URL, as a string.
    :param tags:                Preprocessed tags, as a list object.
    :return:                    A Tumblr submission object
    :onerror:                   Prints error as a string.
    '''
    try:
        client = pytumblr.TumblrRestCleint(consumer_key, consumer_secret, oauth_token, oauth_secret)
        client.create_text(blog_name, state="published", title=title, body=body + '\n' + link_url, tags=tags)
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print("     Tumblr long text error: {}".format(str(e)))


def tumblr_image(consumer_key, consumer_secret, oauth_token, oauth_secret, blog_name, caption, link_url, tags, file_name):
    '''
    Publishes an image post to Tumblr, then deletes it from the queue.

    :param consumer_key:        The account's decrypted consumer key, as a string.
    :param consumer_secret:     The account's decrypted consumer secret, as a string.
    :param oauth_token:         The account's decrypted OAuth token, as a string.
    :param oauth_secret:        The account's decrypted OAuth secret, as a string.
    :param blog_name:           The blog name associated with the cred, as a string.
    :param caption:             The post body, as a string.
    :param link_url:            The link URL, as a string.
    :param tags:                Preprocessed tags, as a list object.
    :param file_name:           The name of the local image file to be uploaded, as a string.
    :return:                    A Tumblr submission object
    :onerror:                   Prints error as a string.
    '''
    try:
        client = pytumblr.TumblrRestCleint(consumer_key, consumer_secret, oauth_token, oauth_secret)
        client.create_photo(blog_name, state="published", caption=caption + '\n' + link_url, tags=tags, data=[file_name])
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print("     Tumblr image error: {}".format(str(e)))


def tumblr_video(consumer_key, consumer_secret, oauth_token, oauth_secret, blog_name, caption, link_url, tags, file_name):
    '''
    Publishes a video post to Tumblr, then deletes it from the queue.

    :param consumer_key:        The account's decrypted consumer key, as a string.
    :param consumer_secret:     The account's decrypted consumer secret, as a string.
    :param oauth_token:         The account's decrypted OAuth token, as a string.
    :param oauth_secret:        The account's decrypted OAuth secret, as a string.
    :param blog_name:           The blog name associated with the cred, as a string.
    :param caption:             The post body, as a string.
    :param link_url:            The link URL, as a string.
    :param tags:                Preprocessed tags, as a list object.
    :param file_name:           The name of the local video file to be uploaded, as a string.
    :return:                    A Tumblr submission object.
    :onerror:                   Prints error as a string.
    '''
    try:
        client = pytumblr.TumblrRestCleint(consumer_key, consumer_secret, oauth_token, oauth_secret)
        client.create_video(blog_name, state="published", caption=caption + '\n' + link_url, tags=tags, data = file_name)
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print("     Tumblr video error: {}".format(str(e)))


def reddit_short_text(client_id, client_secret, user_agent, username, password, target_subreddit, title, body, link_url):
    '''
    Publishes a short text post to Reddit, then deletes it from the queue.

    :param client_id:           The account's decrypted client ID, as a string.
    :param client_secret:       The account's decrypted client secret, as a string.
    :param user_agent:          The app's decrypted user agent, as a string.
    :param username:            The account's decrypted username, as a string.
    :param password:            The account's decrypted password, as a string.
    :param target_subreddit:    The intended subreddit, as a string.
    :param body:                The body of the post, as a string.
    :param link_url:            The link URL, as a string.
    :returns:                   A Reddit submission object.
    :onerror:                   Prints the error as a string.
    '''
    try:
        reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password)
        reddit.subreddit(target_subreddit).submit(title, selftext=body + '\n' + link_url)
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print('     Reddit short text error: {}'.format(str(e)))


def reddit_long_text(client_id, client_secret, user_agent, username, password, target_subreddit, title, body, link_url):
    '''
    Publishes a long text post to Reddit, then deletes it from the queue.

    :param client_id:           The account's decrypted client ID, as a string.
    :param client_secret:       The account's decrypted client secret, as a string.
    :param user_agent:          The app's decrypted user agent, as a string.
    :param username:            The account's decrypted username, as a string.
    :param password:            The account's decrypted password, as a string.
    :param target_subreddit:    The intended subreddit, as a string.
    :param body:                The body of the post, as a string.
    :param link_url:            The link URL, as a string.
    :returns:                   A Reddit submission object.
    :onerror:                   Prints the error as a string.
    '''
    try:
        reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password)
        reddit.subreddit(target_subreddit).submit(title, selftext=body + '\n' + link_url)
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print('     Reddit long text error: {}'.format(str(e)))


def reddit_image(client_id, client_secret, user_agent, username, password, target_subreddit, title, file_name):
    '''
    Publishes an image post to Reddit, then deletes it from the queue.

    :param client_id:           The account's decrypted client ID, as a string.
    :param client_secret:       The account's decrypted client secret, as a string.
    :param user_agent:          The app's decrypted user agent, as a string.
    :param username:            The account's decrypted username, as a string.
    :param password:            The account's decrypted password, as a string.
    :param target_subreddit:    The intended subreddit, as a string.
    :param title:               The post title, as a string.
    :param file_name:           The name of the local image file to be uploaded, as a string.
    :returns:                   A Reddit submission object.
    :onerror:                   Prints the error as a string.
    '''
    try:
        reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password)
        reddit.subreddit(target_subreddit).submit_image(title=title, image_path=file_name)
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print('     Reddit image error: {}'.format(str(e)))


def reddit_video(client_id, client_secret, user_agent, username, password, target_subreddit, title, file_name):
    '''
    Publishes a video post to Reddit, then deletes it from the queue.

    :param client_id:           The account's decrypted client ID, as a string.
    :param client_secret:       The account's decrypted client secret, as a string.
    :param user_agent:          The app's decrypted user agent, as a string.
    :param username:            The account's decrypted username, as a string.
    :param password:            The account's decrypted password, as a string.
    :param target_subreddit:    The intended subreddit, as a string.
    :param title:               The post title, as a string.
    :param file_name:           The name of the local video file to be uploaded, as a string.
    :returns:                   A Reddit submission object.
    :onerror:                   Prints the error as a string.
    '''
    try:
        reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password)
        reddit.subreddit(target_subreddit).submit_video(title=title, video_path=file_name)
        print("     Deleting post from queue...")
        requests.get(f'https://icy-fire.com/api/_d/{x}/auth={read_token}&{delete_token}&{server_id}')
    except Exception as e:
        print('     Reddit video error: {}'.format(str(e)))


def main():
    print("                                //////. /######.                                ")
    print("                            //////* //////* ,#####(                             ")
    print("                          ,///. *#####, //////,(##(.                            ")
    print("                         /  (#####(         ,/,(##(.//                          ")
    print("                         /  (#####(         ,/,(##(.//                          ")
    print("                        ###*,///    /    /     (##(.///                         ")
    print("                        ###*,///      .#*      (##(.///                         ")
    print("                        ###*,///                 ,/////                         ")
    print("                         ##*,/// (           ,//////  .                         ")
    print("                          **,/// #####.  //////* .###                           ")
    print("                            ,/////,.######/  *#####/                            ")
    print("                                ///////.(#######                                ")
    print('\n')
    print("                                               .//                              ")
    print("                                                 ///                            ")
    print("       #(                            (********  /* //                           ")
    print("       #(     /##((##, *#       ,#   (*           /,    / ///.   //**//*        ")
    print("       #(   *#          ,#     *#    (/*******    /,    /,     /*       /.      ")
    print("       #(   #(            #.  /(     (*           /,    /      /,.........      ")
    print("       #(    #/      *     #,((      (*           /,    /      ./.              ")
    print("       (/       /((/        #/       /,           *.    *         .***,         ")
    print("                       *  .#,                                                   ")
    print('\n\n\n')
    print('********************************************************************************')
    print("Initializing Server {}...".format(server_id))
    start = calculate_min(server_id)
    print("Lower bound: {}".format(start))
    end = calculate_max(server_id)
    print("Upper bound: {}".format(end))
    df = create_dataframe(start, end)
    print("Generated reference table: {}".format(str(df.shape())))
    x = current_slot(df)
    print("UTC time now: {}".format(datetime.utcnow().strftime("%A, %B %-d, %Y %H:%M:%f")))
    print("Starting at timeslot {}".format(x))
    print("Running...")

    while x < end + 1:
        print("Querying timeslot {}:".format(x))
        read = requests.get(f'https://icy-fire.com/api/_r/{x}/auth={read_token}&{cred_token}&{server_id}')
        
        if read.status_code == 200:

            if read.json()['platform'] == 'facebook':
                access_token = decrypt(read.json()['access_token'])
                page_id = read.json()['page_id']

                if read.json()['post_type'] == 1:
                    print("     Posting Facebook short text...")
                    facebook_short_text(access_token=access_token, page_id=page_id, body=read.json()['body'], link_url=read.json()['link_url'], tags=read.json()['tags'])
                    print("Done.")

                elif read.json()['post_type'] == 2:
                    print("     Posting Facebook long text...")
                    facebook_long_text(access_token=access_token, page_id=page_id, body=read.json()['body'], link_url=read.json()['link_url'], tags=read.json()['tags'])
                    print("     Done.")

                elif read.json()['post_type'] == 3:
                    print("     Downloading multimedia...")
                    download_multimedia(read.json()['multimedia_url'])
                    print("     Posting Facebook image...")
                    facebook_image(access_token=access_token, page_id=page_id, caption=read.json()['caption'], tags=read.json()['tags'], file_name='./multimedia/{}'.format(read.json()['multimedia_url']))
                    print("     Deleting multimedia...")
                    delete_multimedia(read.json()['multimedia_url'])
                    print("     Done.")

                else:
                    print("     Downloading multimedia...")
                    download_multimedia(read.json()['multimedia_url'])
                    print("     Posting Facebook video...")
                    facebook_image(access_token=access_token, page_id=page_id, caption=read.json()['caption'], tags=read.json()['tags'], file_name='./multimedia/{}'.format(read.json()['multimedia_url']))
                    print("     Deleting multimedia...")
                    delete_multimedia(read.json()['multimedia_url'])
                    print("     Done.")

            elif read.json()['platform'] == 'twitter':
                
                consumer_key = decrypt(read.json()['consumer_key'])
                consumer_secret = decrypt(read.json()['consumer_secret'])
                access_token_key = decrypt(read.json()['access_token_key'])
                access_token_secret = decrypt(read.json()['access_token_secret'])

                if read.json()['post_type'] == 1:
                    print("     Posting Twitter short text...")
                    twitter_short_text(consumer_key=consumer_key, consumer_secret=consumer_secret, access_token_key=access_token_key, access_token_secret=access_token_secret, body=read.json()['body'], link_url=read.json()['link_url'], tags=read.json()['tags'])
                    print("     Done.")

                elif read.json()['post_type'] == 3:
                    print("     Downloading multimedia...")
                    download_multimedia(read.json()['multimedia_url'])
                    print("     Posting Twitter image...")
                    twitter_image(consumer_key=consumer_key, consumer_secret=consumer_secret, access_token_key=access_token_key, access_token_secret=access_token_secret, file_name='./multimedia/{}'.format(read.json()['multimedia_url']), caption=read.json()['caption'], tags=read.json()['tags'], link_url=read.json()['link_url'])
                    print("     Deleting multimedia...")
                    delete_multimedia(read.json()['multimedia_url'])
                    print("     Done.")

                else:
                    print("     Downloading multimedia...")
                    download_multimedia(read.json()['multimedia_url'])
                    print("     Posting Twitter video...")
                    twitter_video(consumer_key=consumer_key, consumer_secret=consumer_secret, access_token_key=access_token_key, access_token_secret=access_token_secret, file_name='./multimedia/{}'.format(read.json()['multimedia_url']), caption=read.json()['caption'], tags=read.json()['tags'], link_url=read.json()['link_url'])
                    print("     Deleting multimedia...")
                    delete_multimedia(read.json()['multimedia_url'])
                    print("     Done.")

            elif read.json()['platform'] == 'tumblr':

                consumer_key = decrypt(read.json()['consumer_key'])
                consumer_secret = decrypt(read.json()['consumer_secret'])
                oauth_token = decrypt(read.json()['oauth_token'])
                oauth_secret = decrypt(read.json()['oauth_secret'])
                blog_name = read.json()['blog_name']

                if read.json()['post_type'] == 1:
                    print("     Posting Tumblr short text...")
                    tumblr_short_text(consumer_key=consumer_key, consumer_secret=consumer_secret, oauth_token=oauth_token, oauth_secret=oauth_secret, blog_name=blog_name, title=read.json()['title'], body=read.json()['body'], link_url=read.json()['link_url'], tags=read.json()['tags'])
                    print("     Done.")

                elif read.json()['post_type'] == 2:
                    print("     Posting Tumblr long text...")
                    tumblr_long_text(consumer_key=consumer_key, consumer_secret=consumer_secret, oauth_token=oauth_token, oauth_secret=oauth_secret, blog_name=blog_name, title=read.json()['title'], body=read.json()['body'], link_url=read.json()['link_url'], tags=read.json()['tags'])
                    print("     Done.")

                elif read.json()['post_type'] == 3:
                    print("     Downloading multimedia...")
                    download_multimedia(read.json()['multimedia_url'])
                    print("     Posting Tumblr image...")
                    tumblr_image(consumer_key=consumer_key, consumer_secret=consumer_secret, oauth_token=oauth_token, oauth_secret=oauth_secret, blog_name=blog_name, caption=read.json()['caption'], link_url=read.json()['link_url'], tags=read.json()['tags'], file_name='./multimedia/{}'.format(read.json()['multimedia_url']))
                    print("     Deleting multimedia...")
                    delete_multimedia(read.json()['multimedia_url'])
                    print("     Done.")

                else:
                    print("     Downloading multimedia...")
                    download_multimedia(read.json()['multimedia_url'])
                    print("     Posting Tumblr video...")
                    tumblr_video(consumer_key=consumer_key, consumer_secret=consumer_secret, oauth_token=oauth_token, oauth_secret=oauth_secret, blog_name=blog_name, caption=read.json()['caption'], link_url=read.json()['link_url'], tags=read.json()['tags'], file_name='./multimedia/{}'.format(read.json()['multimedia_url']))
                    print("     Deleting multimedia...")
                    delete_multimedia(read.json()['multimedia_url'])
                    print("     Done.")

            else:

                client_id = decrypt(read.json()['client_id'])
                client_secret = decrypt(read.json()['client_secret'])
                user_agent = decrypt(read.json()['user_agent'])
                username = decrypt(read.json()['username'])
                password = decrypt(read.json()['password'])
                target_subreddit = read.json()['target_subreddit']

                if read.json()['post_type'] == 1:
                    print("     Posting Reddit short text...")
                    reddit_short_text(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password, target_subreddit=target_subreddit, title=read.json()['title'], body=read.json()['body'], link_url=read.json()['link_url'])
                    print("     Done.")

                elif read.json()['post_type'] == 2:
                    print("     Posting Reddit long text...")
                    reddit_long_text(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password, target_subreddit=target_subreddit, title=read.json()['title'], body=read.json()['body'], link_url=read.json()['link_url'])
                    print("     Done.")

                elif read.json()['post_type'] == 3:
                    print("     Downloading multimedia...")
                    download_multimedia(read.json()['multimedia_url'])
                    print("     Posting Reddit image...")
                    reddit_image(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password, target_subreddit=target_subreddit, title=read.json()['title'], file_name='./multimedia/{}'.format(read.json()['multimedia_url']))
                    print("     Deleting multimedia...")
                    delete_multimedia(read.json()['multimedia_url'])
                    print("     Done.")

                else:
                    print("     Downloading multimedia...")
                    download_multimedia(read.json()['multimedia_url'])
                    print("     Posting Reddit video...")
                    reddit_video(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password, target_subreddit=target_subreddit, title=read.json()['title'], file_name='./multimedia/{}'.format(read.json()['multimedia_url']))
                    print("     Deleting multimedia...")
                    delete_multimedia(read.json()['multimedia_url'])
                    print("     Done.")

        elif read.status_code == 400:
            print("     ERROR: Malformed request; timeslot not found.")
        
        elif read.status_code == 404:
            print("     INFO: Queue is empty; post not found.")

        elif read.status_code == 218:
            print("     INFO: Timeslot not assigned. This is fine.")
        
        else:
            print("     ERROR: Authentication error; check your authentication tokens.")

        x += 1
        print("Sleeping for 60 seconds...")
        time.sleep(60)
        if x == end + 1:
            x = start
    
if __name__ == '__main__':
    main()
