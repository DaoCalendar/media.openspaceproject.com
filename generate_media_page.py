import argparse
import jinja2
import json
import os
import requests
import sys

############
## Header
############

# repo: The repository ("organization/repository") from which we want to retrieve the current commit sha
# auth a HTTPBasicAuth that is used to authenticate the GitHub requests
# returns the current commit sha
def get_current_sha(repo, auth):
  git_commits_url = 'https://api.github.com/repos/{}/commits'.format(repo)
  commit_content = requests.get(git_commits_url, auth=auth).json()
  commit_sha = commit_content[0]['sha']
  print('Remote commit: {}'.format(commit_sha))
  return commit_sha

# previous_commit_hash_file: The full file name of the file that contains the previous hash
# commit_sha: The current commit sha
# returns True if the webpage is current, False otherwise
def webpage_is_current(previous_commit_hash_file, commit_sha):
  if os.path.exists(previous_commit_hash_file):
    with open(previous_commit_hash_file) as f:
      last_commit = f.read()
      print('Last commit: {}'.format(last_commit))
      return last_commit == commit_sha
  else:
    return False

def load_all_files(commit_sha):
  files = []
  def parse_tree(sha, path):
    print(sha)
    git_tree_contents = 'https://api.github.com/repos/{}/git/trees/'.format(args.repo)
    data = requests.get(git_tree_contents + sha, auth=auth).json()
    for t in data['tree']:
      full_path = path + '/' + t['path']
      if t['type'] == 'tree':
        parse_tree(t['sha'], full_path)
      elif t['type'] == 'blob':
        files.append(full_path)
      else:
        print('unknown type {}'.format(t['type']))
  parse_tree(commit_sha, '')
  return files

def filtered_files(files):
  image_extensions = [ '.png', '.jpg', '.jpeg' ]
  video_extensions = [ '.video' ]
  for file in files:
    path_components = os.path.splitext(file)
    extension = path_components[1].lower()
    # We might have additional files that we want to ignore, a prominent example being README.md
    if not ((extension in image_extensions) or (extension in video_extensions)):
      files.remove(file)

  return files

############
## Main
############

desc = 'Generates a static webpage with images and videos for the http://media.openspaceproject.com webpage, based off the content on a GitHub repository'

parser = argparse.ArgumentParser(description=desc, epilog='')
parser.add_argument('repo', metavar='<repository>', type=str, help='The org+repo where the media is hosted; for example:  OpenSpace/media.openspaceproject.com')
parser.add_argument('dest', metavar='<destination>', type=str, help='The location where the static webpage will be written to')
parser.add_argument('username', metavar='<GitHub user name>', type=str, help='The user name on GitHub that is used for the requests')
parser.add_argument('token', metavar='<GitHub token>', type=str, help='The token that is associated with the user name')
args = parser.parse_args()

# This file contains the hash of the commit when we last ran this script, if that hash is
# the same as the current one, then we don't need to recreate the static page, as nothing
# has changed
previous_commit_hash_file = args.dest + '/last_commit'
auth = requests.auth.HTTPBasicAuth(args.username, args.token)

commit_sha = get_current_sha(args.repo, auth)
if not os.path.exists(args.dest):
    print('Creating directory {}'.format(args.dest))
    os.makedirs(args.dest)

if webpage_is_current(previous_commit_hash_file, commit_sha):
  sys.exit()

# raw_files contains a list of all raw files from the source tree, without any postprocessing
raw_files = load_all_files(commit_sha)
files = filtered_files(raw_files)
print('raw_files', raw_files)
print('files', files)

# Now we are doing the post processing to provide richer information
files = []
all_tags = ''
image_extensions = [ '.png', '.jpg', '.jpeg' ]
video_extensions = [ '.video' ]
for file in raw_files:
  path_components = os.path.splitext(file)
  extension = path_components[1].lower()

  # txt files are used for additional information about images, such as captions,
  # attributions etc. We are explicitly looking for these, so we can safely jump over these
  # here
  if extension == '.txt':
    continue
  # We might have additional files that we want to ignore, a prominent example being README.md
  if not ((extension in image_extensions) or (extension in video_extensions)):
    continue

  f = {
    'path': file,
    'tags': '',
    'url': 'https://raw.github.com/{}/master{}'.format(args.repo, file)
  }
  comps = path_components[0].split('/')[1:-1]
  f['tags'] = ' '.join(comps)
  all_tags = all_tags + ' ' + ' '.join(comps)


  desc_file = path_components[0] + '.txt'
  if desc_file in raw_files:
    req = requests.get('https://raw.github.com/{}/master{}'.format(args.repo, desc_file))
    tags = req.text.split('\n')[0]
    description = '\n'.join(req.text.split('\n')[1:])
    f['tags'] = f['tags'] + ' ' + tags
    all_tags = all_tags + ' ' + tags
    f['description'] = description

  if extension in image_extensions:
    f['type'] = 'image'
    files.append(f)

  if extension in video_extensions:
    f['type'] = 'video'
    req = requests.get(f['url'])
    f['video'] = req.text
    files.append(f)

# The list starts with an empty character which we don't want
all_tags = all_tags[1:].split(' ')
# Make the list unique
all_tags = list(set(all_tags))
all_tags.sort()

tag_infos = []
for t in all_tags:
  tag_infos.append({ 'identifier': t })


with open('tag-naming.txt') as f:
  content = f.read();
  lines = content.split('\n')
  
  for l in lines:
    tag = l.split(' ')[0]
    name = ' '.join(l.split(' ')[1:])

    for t in tag_infos:
      if t['identifier'] == tag:
        t['name'] = name

env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'), autoescape=jinja2.select_autoescape([ 'html', 'xml' ]))
# template = env.get_template('index.html.jinja')
template = env.get_template('index.html.jinja')
res = template.render(items=files, tags=tag_infos)
with open(args.dest + '/index.html', 'w') as f:
  f.write(res)
