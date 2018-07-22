# Agenda Tracker

The results are right here: https://twitter.com/baysurveillance

A Twitter bot that looks through city agenda PDFs for developer-defined regular expressions.
When the bot finds a match, it tweets a match with the date, matching terms, and a link to the file.

Step 1. Register a twitter account and create a new app. 

Step 2. Find your city's Legistar or other site.
        Copy the details of the site into the config.json file.

Step 3. Update the search term regular expressions for your desire terms. Each term will be concatenated by the OR operator and will only find matches for your terms preceded by white space ('\b') - ie. the beginning of a word/phrase so "alpr" does not match with "malpractice".  

Step 4. Test run the python script in an environment with Python 3 and the required libraries (see import statements). You'll need to run the script in the same folder as agenda_log.csv (delete the old data, just leave the headers) and the config.json. 

Step 5. Once you get it working, put the credentials from the twitter app (don't post these online) into the config file and uncomment the relevant tweepy code in the script.

Step 6. Test the script again - it should now tweet to the twitter account. You may need to delete a few lines in the agenda_log so that the script doesn't ignore all the agendas.

Step 7. Create a scheduled task to run the script on your own computer. If your computer is not always on and connected to the internet, you may want to use a cloud service. Keep in mind you'll need an environment (virtual or otherwise) with Python3. I use PythonAnywhere, but you'll need a paid account to scrape Https sites (like Legistar).  