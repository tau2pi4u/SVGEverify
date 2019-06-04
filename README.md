# SVGEVerify
Required libraries
`discord, oauth2, gspread`
A google service account is also needed to handle the gspread, and the file client_secret.json needs to be where it is indicated by the config.
A gmail account with the email and pw in the config and smtp enabled is also needed to send the emails. 
A discord bot key should also be put in the config. 
The rest of the config should be filled out with the true values based on the example config and given as a launch option or named config.json (default).
The roles "student" and "guest" are required, other are optional. 