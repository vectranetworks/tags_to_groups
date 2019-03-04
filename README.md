# Tags2Groups

Tags2Groups.py is a python script to turn existing host tags into the new Cognito Host Group feature. 

## Prerequisites

Python3, and requests module.  A Vectra API key is also required and can be generated by going to My Profile and Generating an API token.

### Running

When ran, the script needs to be given a direction, either pull (read) or push (write). 


```
python3 tags2groups.py --pull https://vectra.local AAABBBCCCDDDEEEFFF
python3 tags2groups.py --push https://vectra.local AAABBBCCCDDDEEEFFF
```

The --pull flag will read all the host tags from the system and put them into the file tags_groups.txt. This file is populated with all hosts tags and the corresponding group name divided by a |, one per line. The --active flag will limit the tags pulled to only active hosts on your system.

Each line in the output file has two parts. Everything to the left of the | is read as tags and everything to the right is the name of the group the tag is to be converted to. Multiple tags can be converted to the same group. This

The --push flag will convert the tags listed in tags_groups.txt into groups. If you previously ran the --pull flag, you will need to delete any tags you do not want to convert. You do not need to pre-create the group, the script will handle that automatically. The --poptag will remove the tag from the host once it has been added to a group. NOTE: THIS IS NOT UNDOABLE! Be sure to remove any tags from the file you do not want to convert to a group.

## Typical Usage
```
python3 tags2groups.py --pull https://vectra.local AAABBBCCCDDDEEEFFF
```
Edit tag_groups.py deleting unwanted conversions and changing group names where appropriate
```
python3 tags2groups.py --push https://vectra.local AAABBBCCCDDDEEEFFF
```

## Recommendations
When the tag to group mapping file is updated by the user to reflect the desired mappings, run with the --push flag initially initially without the --poptag flag and then review Cognito Detect brain for desired outcome.  Any improper mappings can be easily reverted by deleting the group under the "Host Groups" tab of the "Manage" page.
Once the mappings are correct, if desired, you can rerun the script with the --push and --poptag flags to remove the tags specified in the tags to group mapping file.

## Logging
Informational messages are displayed to standard output indicating the hosts being added to groups.  This information is also written to the tags2groups.log file in the local directory.

### Help Output
usage: tags2groups.py [-h] [--pull] [--push] [--poptag] [--active]
cognito_url cognito_token

Add tagged hosts to group(s) based on tag.

positional arguments:
cognito_url    Cognito's brain url, eg https://brain.vectra.local
cognito_token  Cognito's API token, eg AAABBBCCCDDDEEEFFF

optional arguments:
-h, --help     show this help message and exit
--pull         Poll for hosts with tags, writes output to file for editing
--push         Adds or updates groups based on tag, reads input from file
--poptag       Used in conjunction with --push option, removes tag from host utilized to identify group
--active       Only work on hosts with active detections, used in conjunction with --pull or --push

Run with --pull to generate a file with suggested tag to group mappings.
Example: tags2groups.py https://vectra.local AAABBBCCCDDDEEEFFF --pull

Edit tags_groups.txt file to adjust tag to group mappings as desired

Run with --push to generate groups and assign tagged hosts to those groups
Example: tags2groups.py https://vectra.local AAABBBCCCDDDEEEFFF --push


## Authors

* **Matt Pieklik** - *Initial work*

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
