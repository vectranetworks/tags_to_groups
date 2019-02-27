#!/usr/bin/env python3

__title__ = 'Assign hosts to groups based on tags'
__version__ = '1.0RC1'
__author__ = 'mp@vectra.ai'
__copyright__ = 'Vectra AI, Inc.'
__status__ = 'Production'
__license__ = 'Released under the  MIT License'

'''
Script that pulls hosts with tags, generates a file with a one-to-one tag to group relationship based on those tags.  
Tag to group relationship file should be edited prior to utilizing the --push option to define the desired tag to group
(tag|group) relationship.  Written for python3.
'''

try:
    import sys
    import requests
    import argparse
    import logging
    import json
    import logging.handlers
    import re
except ImportError as error:
    StringError = "\nMissing import requirements: %s\n" % str(error)
    sys.exit(StringError)


#  Logging setup
syslog_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

requests.packages.urllib3.disable_warnings()

# Default filename for tag to group mapping
tag_file = 'tags_groups.txt'

parser = argparse.ArgumentParser(description='Add tagged hosts to group(s) based on tag.',
                                 prefix_chars='-', formatter_class=argparse.RawTextHelpFormatter,
                                 epilog='Run with --pull to generate a file with suggested tag to group mappings.\n'
                                        'Example: tags2groups.py https://vectra.local AAABBBCCCDDDEEEFFF --pull\n\n'
                                        'Edit tags_groups.txt file to adjust tag to group mappings as desired\n\n'
                                        'Run with --push to generate groups and assign tagged hosts to those groups\n'
                                        'Example: tags2groups.py https://vectra.local AAABBBCCCDDDEEEFFF --push')

parser.add_argument('cognito_url', type=str, help='Cognito\'s brain url, eg https://brain.vectra.local')
parser.add_argument('cognito_token', type=str, help='Cognito\'s API token, eg AAABBBCCCDDDEEEFFF')
parser.add_argument('--pull', action='store_true', default=False,
                    help='Poll for hosts with tags, writes output to file for editing')
parser.add_argument('--push', action='store_true', default=False,
                    help='Adds or updates groups based on tag, reads input from file')
parser.add_argument('--poptag', action='store_true', default=False,
                    help='Used in conjunction with --push option, removes tag from host utilized to identify group')
parser.add_argument('--active', action='store_true', default=False,
                    help='Only work on hosts with active detections, used in conjunction with --pull or --push')
args = parser.parse_args()


vectra_header = {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache',
    'Authorization': 'Token ' + args.cognito_token
}
api = '/api/v2/'
page_size = '5000'
vectra_tag_uri = '/api/v2/tagging/host/'


def test_creds(url, headers):
    try:
        response = requests.request("GET", url, headers=headers, verify=False)
        if response.status_code in [200, 201]:
            return
        else:
            syslog_logger.info('Error code: {}, Credential errors: {}'.format(response.status_code, response.content))
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        syslog_logger.info('\nUnable to establish connection with brain: {}\n\n'.format(args.cognito_url))
        sys.exit(1)


def poll_vectra_tags(url, headers):
    #  Returns a set of tags
    response = requests.request("GET", url, headers=headers, verify=False).json()['results']

    tag_list = []
    for tag_key in response:
        tag_list += tag_key['tags']
    return sorted(set(tag_list))


def poll_vectra_hosts(url, headers):
    #  Returns a list of host IDs
    response = requests.request("GET", url, headers=headers, verify=False).json()['results']
    id_list = []
    for hid in response:
        id_list.append(hid['id'])
    return id_list


def gen_tag_file(tags):
    #  Writes the suggested list of tags to group mappings to a file
    with open(tag_file, 'w') as write_file:
        write_file.write("# Separate multiple tags relating to one group with a ',' no spaces between tags.\n"
                         "# Group illegal characters: ! @ % & * ) ( \n"
                         "# Separate the tag(s) and relating group with a '|' with no spaces\n"
                         "# Tag and group relation format examples:\n#tag123|group123\n#Role1,Role two:"
                         "Webserver|group1\n#\n"
                         "# Tags and suggested group names:\n")
        for tag in tags:
            write_file.write("{0}|{0}\n".format(tag))
        write_file.close()


def process_tag_file():
    #  Returns a dictionary of groups and tags
    #  'test1' : ['test1', 'test2']
    group_tag = {}
    comment_chars_re = '^[#].*'
    with open(tag_file, 'r') as read_file:
        for line in read_file:
            comment = re.search(comment_chars_re, line.strip())
            if comment:
                pass
            else:
                tag, group = line.strip().split('|')
                group_tag[group] = tag.split(',')
    read_file.close()
    return group_tag


def add_host_to_group(group, host_ids):
    #  Adds a list of hosts to a group, creating the group if needed
    body_dict = {
        "name": group,
        "description": "Created by script",
        "type": "host",
        "members": host_ids
    }
    body = json.dumps(body_dict)

    #  Check to see if group already exists
    cognito_group_check_url = args.cognito_url + api + 'groups/?name=' + group
    group_results = requests.request("GET", url=cognito_group_check_url, headers=vectra_header, verify=False).json()
    syslog_logger.debug('Group results:{}'.format(group_results))
    if not group_results:
        #  Group does not exist
        cognito_group_url = args.cognito_url + api + 'groups/'
        response = requests.request("POST", url=cognito_group_url, headers=vectra_header, data=body, verify=False)
        syslog_logger.debug('Group: {} does not exist, response:{}'.format(group, response))
    else:
        syslog_logger.debug('Group like: {} exists'.format(group))
        #  Group exists, possible fuzzy match
        for item in group_results:
            if item['name'] == group:
                group_id = item['id']
                #  Handle pre-existing members of group
                pre_exist_members = []
                for member in item['members']:
                    pre_exist_members.append(member['id'])
                #  Combine existing hosts with updated hosts and remove duplicates
                host_id_list = list(set(pre_exist_members + host_ids))
                cognito_group_url = args.cognito_url + api + 'groups/' + str(group_id)
                syslog_logger.debug('group URL:{}'.format(cognito_group_url))
                body_dict = {
                    "members": host_id_list
                }
                body = json.dumps(body_dict)
                response = requests.request("PATCH", url=cognito_group_url, headers=vectra_header,
                                            data=body, verify=False)
                syslog_logger.debug('Group: {} exists, response:{}'.format(group, response))
            else:
                cognito_group_url = args.cognito_url + api + 'groups/'
                response = requests.request("POST", url=cognito_group_url, headers=vectra_header, data=body,
                                            verify=False)
                syslog_logger.debug('Group like: {} does not exist, response:{}'.format(group, response))


def process_hosts(group_dict):
    #  Passed a dictionary of Groups and associated tags in a list
    #  {'G 22': ['T 22'], 'G 23': ['T 23'], 'G1': ['T1'], 'G2': ['T2'], 'G3': ['T3', 'T1']}
    #  Calls add_host_to_group, and remove_tags methods
    for key, tag in group_dict.items():
        tag_list = []
        cognito_tagged_host_url = args.cognito_url + api + 'search/hosts/?page_size=' + \
            page_size + '&field=id&query_string='
        if args.active:
            cognito_tagged_host_url += 'host.state:"active" AND '
        if len(tag) == 1:
            cognito_tagged_host_url += 'host.tags:"{}"'.format(tag[0])
            syslog_logger.debug(cognito_tagged_host_url)
            tag_list.append(tag[0])
        else:
            syslog_logger.debug('tag list:\"{}\"'.format(tag))
            list_len = len(tag) - 1
            count = 0
            cognito_tagged_host_url += '(host.tags:'
            while count <= list_len:
                if count == list_len:
                    cognito_tagged_host_url += ' OR "{}")'.format(tag[count])
                    tag_list.append(tag[count])
                    count += 1
                elif count == 0:
                    cognito_tagged_host_url += '"{}"'.format(tag[count])
                    tag_list.append(tag[count])
                    count += 1
                else:
                    cognito_tagged_host_url += ' OR "{}"'.format(tag[count])
                    tag_list.append(tag[count])
                    count += 1
            syslog_logger.debug(cognito_tagged_host_url)

        ids = poll_vectra_hosts(cognito_tagged_host_url, vectra_header)
        if args.poptag:
            #  Call update_tags with list of Host IDs and tag to be removed
            syslog_logger.debug('Host_ids:{}, tag_list:{}'.format(ids, tag_list))
            remove_tags(ids, tag_list)
        syslog_logger.debug('Group:{}, ids:{}'.format(key, ids))
        add_host_to_group(key, ids)


def remove_tags(hostid_list, remove_list):
    #  Called with list of host IDs and a list of tags to remove from those hosts
    #  Removes tags from host, gracefully handles trying to remove a non-existent tag
    for hostid in hostid_list:
        urlp = args.cognito_url + vectra_tag_uri + str(hostid)
        urlq = urlp + '?fields=tags'
        syslog_logger.debug('Update_tags url:%s', urlp)
        tags = requests.get(url=urlq, headers=vectra_header, verify=False).json()['tags']
        for remove in remove_list:
            try:
                tags.remove(remove)
            except ValueError:
                continue

        body = json.dumps({'tags': tags})
        r = requests.patch(url=urlp, headers=vectra_header, data=body, verify=False)
        syslog_logger.debug('Tag patch results:{}'.format(r))


if __name__ == '__main__':
    if args.pull:
        test_creds(args.cognito_url + api, vectra_header)
        #  Pull tags from hosts (first step)
        if args.active:
            #  Only pull tags from active hosts
            syslog_logger.info('Collecting active hosts with tags')
            cognito_full_url = args.cognito_url + api + 'search/hosts/?page_size=' + page_size + '&field=tags' + \
                '&query_string=host.state:"active" AND host.tags:*'
        else:
            #  Pull tags from all hosts
            syslog_logger.info('Collecting all hosts with tags')
            cognito_full_url = args.cognito_url + api + 'search/hosts/?page_size=' + page_size + '&field=tags' + \
                '&query_string=host.tags:*'
        syslog_logger.debug('URL:{}'.format(cognito_full_url))
        tags = poll_vectra_tags(cognito_full_url, vectra_header)
        syslog_logger.debug('Tags:{}'.format(tags))
        gen_tag_file(tags)
        print('\nStep 1.  Edit {} and define tag to group relationship.\nStep 2.  Rerun script with --push flag\n'
              .format(tag_file))
    elif args.push:
        test_creds(args.cognito_url + api, vectra_header)
        #  Import group and tag relationship from file
        syslog_logger.info('Adding hosts to groups')
        groups = process_tag_file()
        syslog_logger.debug(groups)
        #  Collect dictionary of hosts with those tags
        #  Process hosts to add tags
        process_hosts(groups)
    else:
        print('Specify --pull to pull tags from hosts, or --push to create groups and add hosts to groups.')

