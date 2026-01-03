Make adding a new discord channel a bit easier. It currently requires chanegs in the following areas.
    Add Model - models.py
    Add Admin Pages - admin.py
    Create new Gemini Prompt - gemini.py
    Create new code to add signal return to Database - gemini.py
    Modifications to Bandit to send proper channel name to django

Modify bandit to send signals to local django server for development using tunnels

Create a way for Bandit to determine if signal is cancelled and cancel associated trades

Create a function to monitor real-time prices of open orders and invalidate

Create a user interface

Do some code refactoring

Try to come up with encryption plan

Add API authentication methods

Add password auth for TV Signals

Look at open deals and refine dupe logic to account for not a dupe signal but another trade on the same pair
