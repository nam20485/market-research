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

Keep it simple and easy to implement and maintain.

### Language and Package Management

- Python
- uv package management

### Frontend

Recommend: easiest and simplest. Vite? 


### Backend

- litellm for inference using openai and other models
- fastapi for the api


### Configuration

environment variables/`.env` for the api key and other configuration

### Containerization

- docker for containerization
- docker-compose for the docker-compose file

### Deployment

- github actions for the deployment
- cloudflare worker and DNS for the deployment
- follow existing deployment pattern found in GH repo:
    - `intel-agency/intel-agency-com-v2` (`/home/nam20485/src/github/intel-agency`)

**DO NOT ACTUALLY DEPLOY YET- USER WILL MERGE TO RELEASE BRANCH MANUALLY WHEN READY TO DEPLOY**
