import argparse
import jinja2
import json
import os
import requests
import sys

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

git_commits_url = 'https://api.github.com/repos/{}/commits'.format(args.repo)
git_tree_contents = 'https://api.github.com/repos/{}/git/trees/'.format(args.repo)

commit_content = requests.get(git_commits_url, auth=auth).json()
commit_sha = commit_content[0]['sha']
print('Remote commit: {}'.format(commit_sha))

if not os.path.exists(args.dest):
    print('Creating directory {}'.format(args.dest))
    os.makedirs(args.dest)

if os.path.exists(previous_commit_hash_file):
  with open(previous_commit_hash_file) as f:
    last_commit = f.read()
    print('Last commit: {}'.format(last_commit))
    if last_commit == commit_sha:
      # The already created page was created with the most current hash, so we have
      # nothing to do
      sys.exit()

# If we get here, then it has been determined that we need to recreate the webpage

# raw_files contains the raw information from the source tree, without any postprocessing
raw_files = []
def parse_tree(sha, path):
  print(sha)
  data = requests.get(git_tree_contents + sha, auth=auth).json()
  for t in data['tree']:
    full_path = path + '/' + t['path']
    if t['type'] == 'tree':
      parse_tree(t['sha'], full_path)
    if t['type'] == 'blob':
      raw_files.append(full_path)
parse_tree(commit_sha, '')

# Now we are doing the post processing to provide richer information
files = []
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
    'type': 'image',
    'url': 'https://raw.github.com/{}/master{}'.format(args.repo, file)
  }

  desc_file = path_components[0] + '.txt'
  if desc_file in raw_files:
    req = requests.get('https://raw.github.com/{}/master{}'.format(args.repo, desc_file))
    f['description'] = req.text

  if extension in image_extensions:
    f['type'] = 'image'
    files.append(f)

  if extension in video_extensions:
    f['type'] = 'video'
    req = requests.get(f['url'])
    f['video'] = req.text
    files.append(f)

grouped_files = {
  'name': 'root',
  'files': [],
  'directories': []
}
for f in files:
  path = f['path']
  # We need to remove the first and last part of the path;  the first part is always empty
  # as all paths start with a leading '/' and the last part of the path is the filename
  path_components = path.split('/')[1:-1]

  def add_to_dictionary(dict, components, file):
    def find_directory(dict, name):
      for d in dict:
        # We are trying to find whether we have visited this directory before
        if d['name'] == name:
          return d
      return None

    if len(components) == 0:
      # If there are no more components, we have to be dealing with a file here
      if not dict['files']:
        dict['files'] = []
      dict['files'].append(file)
    else:
      front = components[0]
      if not dict['directories']:
        dict['directories'] = []

      pos = find_directory(dict['directories'], front)
      if pos is None:
        dict['directories'].append({
          'name': front,
          'files': [],
          'directories': []
        })
        pos = find_directory(dict['directories'], front)

      add_to_dictionary(pos, components[1:], file)

  add_to_dictionary(grouped_files, path_components, f)


env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'), autoescape=jinja2.select_autoescape([ 'html', 'xml' ]))
template = env.get_template('index.html.jinja')
res = template.render(items=grouped_files)
with open(args.dest + '/index.html', 'w') as f:
  f.write(res)
