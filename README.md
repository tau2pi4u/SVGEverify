# SVGEVerify
## Python
Python 3.6 or greater is required
### Libraries
`discord, oauth2, gspread, oauth2client`  

## Google Drive
A google service account is also needed to handle the gspread, and the file client_secret.json needs to be where it is indicated by the config.  
The drive should contain two sheets: 
* `verify_backup`, which should be in the top level of the drive.
* `member_data`, the id of which should be in the config  

### verify_backup
This backup will be filled in by the bot, so leave it empty

### member_data
This should contain two columns: `email` and `level`. The levels should be the names you gave the various roles in the config file. This allows different membership tiers. For SVGE we had: `student`, `community member` (people who'd signed up on the SU website) and `committee`.

Make a file called credentials.json using the following guide:  
Read: https://developers.google.com/drive/api/v3/quickstart/python  


Make a file called client_secret.json using the following guide:  
Read: https://gspread.readthedocs.io/en/latest/oauth2.html

## Email
A gmail account with the email and pw in the config and smtp enabled is also needed to send the emails. To enable smtp you need to enable less secure apps and because of this + the pw being stored in plaintext, a throwaway email is strongly recommended.  

## Discord bot
A discord bot key should also be put in the config.   
Read: https://discordpy.readthedocs.io/en/latest/discord.html

## Config
The rest of the config should be filled out with the true values based on the example config and given as a launch option or named config.json (default).  
The roles "committee", "student" and "guest" are required, others are optional.