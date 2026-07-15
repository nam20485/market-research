# Plan

## Description

Create a UI app that conducts used market price and sales research and creates sale listing content for target online marketplaces for used items the user enters

## Requirements and UI Flow
 
Create content compatible with FB marketplace and Offerup market listings. 

Identify Item:

- Ask the user about the item they want to list. Gather details and any pictures the user can attach for context.
- Search for the item
- Ask for more info if the specific items can't be found
- Repeat until you have a lock on the specific item

- Gather Market Research
- Create used market research report (used prices, demand, optimal marketing angle), etc.

- If user approves:

Create market listing content (title, description body, etc.) in target market format
for inference

## Tech Stack

- Python
- uv package management

### Frontend

Recommend: easiest and simplest. Vite? 


### Backend

- litellm for inference using openai and other models
- fast api for the api

Python:

- uv
- fastapi
- litellm 

