from telethon.sync import TelegramClient
from telethon import functions, types

import requests
import json
import shutil
import os
import yaml


def find_all_groups_by_name(response, name):
    matcher = lambda x: name.lower() in x['name'].lower()
    return list(filter(matcher, response['items']))


def find_group_by_name(response, name):
    return find_all_groups_by_name(response, name)[0]


def extract_photos_urls(attachments, mode='z'):
    """
    input:
        mode: str - s, m, o, p, q, x, y, z
    """
    SIZES = ['s', 'm', 'o', 'p', 'q', 'x', 'y', 'z']
    result = []
    photos = filter(lambda x: x['type']=='photo', attachments)
    photos = (x['photo'] for x in photos)
    for photo in photos:
        sizes_ids = [x['type'] for x in photo['sizes']]
        modes_sorted = filter(lambda x: x in sizes_ids, SIZES)
        max_mode = max(enumerate(modes_sorted), key=lambda x: x[0])[1]
        for size in photo['sizes']:
            if size['type'] == max_mode:
                result.append(size['url'])
                break
    return result


def save_image(url, path):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(path, 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)


def save_post_images(post, base_path='./'):
    if 'attachments' not in post:
        return
    post_id = str(post['id']).zfill(5)
    post_dir = os.path.join(base_path, f'post_{post_id}')
    if os.path.exists(post_dir):
        print(f'Post {post_id} is already saved')
        return
    os.makedirs(post_dir, exist_ok=True)
    photos_urls = extract_photos_urls(post['attachments'])
    for cnt, url in enumerate(photos_urls):
        save_image(url, os.path.join(post_dir, 'im_'+str(cnt).zfill(2)+'.jpg'))


def save_wall(response, base_path='./'):
    for post in response['items']:
        save_post_images(post, base_path)
        print(post['text'])


class VkClient:
    api_base = "https://api.vk.com/method/"

    def __init__(self, access_token):
        self.access_token = access_token

    def get_groups(self, user_id, extended=1):
        url_groups = f"{self.api_base}groups.get?v=5.131&access_token={self.access_token}" + \
                     f"&user_id={user_id}&extended={extended}"
        response = requests.get(url_groups)
        groups = json.loads(response.content)
        return groups['response']

    def get_wall(self, owner_id, wall_count=100):
        url_wall = f"{self.api_base}wall.get?v=5.131&access_token={self.access_token}" + \
                   f"&owner_id={owner_id}&count={wall_count}"
        response_wall = requests.get(url_wall)
        posts = json.loads(response_wall.content)
        return posts['response']


if __name__ == '__main__':
    settings_path = './settings.yml'
    with open(settings_path, "r") as stream:
        try:
            settings = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    tg_cfg = settings['telegram']
    vk_cfg = settings['vk']
    group_name = "андрей"

    vk = VkClient(vk_cfg['token'])
    groups = vk.get_groups(vk_cfg['user_id'])
    group = find_group_by_name(groups, group_name)
    wall = vk.get_wall(-group['id'])

    with TelegramClient(tg_cfg['username'], tg_cfg['api_id'], tg_cfg['api_hash']) as client:
        result = client(functions.channels.CreateChannelRequest(
            title='SomeTitle1',
            about='some string here',
            megagroup=True,
            for_import=True
        ))
        print(result.stringify())

        inp_channel = client.get_input_entity(result.chats[0])
        print(inp_channel)

        users = [client.get_input_entity(x) for x in tg_cfg['test_users']]
        print(users)
        result = client(functions.channels.InviteToChannelRequest(
            channel=inp_channel,
            users=users
        ))
        for post in sorted(wall['items'], key=lambda x: x['id']):
            post_id = str(post['id']).zfill(5)
            text = post['text']
            save_post_images(post, vk_cfg['images_path'])

            if post['text'] != '':
                client.send_message(inp_channel, post['text'])
            try:
                client.send_file(inp_channel, f'{vk_cfg["images_path"]}/post_{post_id}/im_00.jpg')
            except Exception as e:
                print(e)

        print(result.stringify())
