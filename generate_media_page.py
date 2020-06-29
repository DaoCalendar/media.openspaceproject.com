import argparse
import jinja2
import json
import os
import requests
import sys

##############
##  Header  ##
##############

CurrentVersion = 1.0

# class TagMapping:
#   def __init__(self, identifier, name):
#     self.identifier = identifier
#     self.name = name

#   def __repr__(self):
#     return '{{ {}: {} }}'.format(self.identifier, self.name)

class Configuration:
  # file: File containing the configuration information
  def __init__(self, file):
    with open(file) as f:
      data = json.load(f)
      self.version = data['version']
      self.tags = data['tags']
      # self.tags = []

      # # Convert from the JSON format to a flat list
      # for key in data['tags']:
      #   self.tags.append(TagMapping(key, data['tags'][key]))

  def __repr__(self):
    return '{{ Version: {}, Tags: {}'.format(self.version, self.tags)

class File:
  TypeImage = 'image'
  TypeVideo = 'video'

  def __init__(self):
    # The type of this file. Should be TypeImage or TypeVideo
    self.type = ''
    # The local path to the file in the repository
    self.path = '';
    # The full URL to get to the file in the repository
    self.url = '';
    # A list of tags that are applied to this file
    self.tags = '' # @TODO Change to array
    # The full descriptive text for this file
    self.description = ''

  def __repr__(self):
    return '{{ Type: {}\tPath: {}\tURL: {}\tTags: {}\tDescription: {} }}'.format(self.type, self.path, self.url, self.tags, self.description)


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

# commit_sha: The hash of the comit for which all files should be loaded
# returns A list of all files with full path and a leading '/' character
def load_all_files(commit_sha):
  files = []
  def parse_tree(sha, path):
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

# file: The path to a file
# returns True if the file is an image file, False otherwise
def is_image_file(file):
  path_components = os.path.splitext(file)
  extension = path_components[1].lower()
  return extension in [ '.png', '.jpg', '.jpeg' ]

# file: The path to a file
# returns True if the file is an video file, False otherwise
def is_video_file(file):
  path_components = os.path.splitext(file)
  extension = path_components[1].lower()
  return extension in [ '.video' ]

# files: A list of all files
# returns A filtered list that only contains images or videos
def filtered_files(files):
  result = []
  for file in files:
    # We might have additional files that we want to ignore, a prominent example being README.md
    if is_image_file(file) or is_video_file(file):
      result.append(file)
  return result

def classify_files(repo, files):
  def split_by_folder(t):
    comps = t.split('/')[1:-1]
    return ' '.join(comps)

  result = []
  for file in files:
    path_components = os.path.splitext(file)
    extension = path_components[1].lower()
    url = 'https://raw.github.com/{}/master{}'.format(repo, file)

    f = File()
    f.path = file
    f.tags = split_by_folder(path_components[0])

    if is_image_file(file):
      f.type = File.TypeImage
      f.url = url
    if is_video_file(file):
      f.type = File.TypeVideo
      req = requests.get(url)
      f.url = req.text
    result.append(f)
  return result

def add_descriptions(repo, files, all_files):
  def parse_description(text):
      data = json.loads(text)
      print('aaa', data)
      return ' '.join(data['tags']), data['desc']
      # tags = text.split('\n')[0]
      # description = '\n'.join(text.split('\n')[1:])
      # return tags, description

  for file in files:
    path_components = os.path.splitext(file.path)
    desc_file = os.path.splitext(file.path)[0] + '.json'
    if desc_file in all_files:
      req = requests.get('https://raw.github.com/{}/master{}'.format(repo, desc_file))
      tags, desc = parse_description(req.text)
      file.tags = file.tags + ' ' + tags
      file.description = desc

# files: An array of classified files
# returns A sorted flat list of all unique tags
def collect_tags(files):
  tags = []
  for file in files:
    ts = file.tags.split(' ')
    tags = tags + ts
  tags = list(set(tags))
  tags.sort()
  return tags


############
##  Main  ##
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

print('Load configuration')
config = Configuration('config.json')
if config.version != CurrentVersion:
  print('Configuration file version {} different from current version {}'.format(config.version, CurrentVersion))

print('Retrieve current SHA')
commit_sha = get_current_sha(args.repo, auth)
if not os.path.exists(args.dest):
    print('Creating directory {}'.format(args.dest))
    os.makedirs(args.dest)

print('Check if webpage is current')
if webpage_is_current(previous_commit_hash_file, commit_sha):
  sys.exit()

print('Load all files')
raw_files = load_all_files(commit_sha)
# print('rf', raw_files)

print('Filter files')
files = filtered_files(raw_files)
# print('f', files)

print('Classifying files')
classified_files = classify_files(args.repo, files)
# print('c', classified_files)

print('Load descriptions')
add_descriptions(args.repo, classified_files, raw_files)
# print('cd', classified_files)

print('Collect tags')
all_tags = collect_tags(classified_files)
print('at', all_tags)


print('Creating page')
env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'), autoescape=jinja2.select_autoescape([ 'html', 'xml' ]))
# template = env.get_template('index.html.jinja')
template = env.get_template('index.html.jinja')
res = template.render(items=classified_files, all_tags=all_tags, tag_names=config.tags)

print('Writing page')
with open(args.dest + '/index.html', 'w') as f:
  f.write(res)
