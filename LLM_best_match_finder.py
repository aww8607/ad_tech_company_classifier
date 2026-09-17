import pandas as pd
import sqlite3
from google import genai
import sys
import os
from firecrawl import FirecrawlApp

sys.stdout.reconfigure(encoding='utf-8')



client = genai.Client(api_key="##############")

FIRECRAWL_API_KEY = "#################"

#Create a one sentence summary of the website content using the Gemini 2.5 Flash model. The summary should focus on the main value proposition, key features, and any calls to action. The output should be concise and only return the text without any additional formatting or JSON structure.
def summarize_website(url):
    
    app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    print(f"Visiting {url}...")

    #Scrape the website content, including the main content and any relevant metadata. Set a max age of 48 hours (172800000 milliseconds) to ensure the content is relatively fresh. Use parsers that can handle PDF content and format the output in markdown for better readability.
    web_content = app.scrape(
        url, 
        only_main_content=False, 
        max_age=172800000,
        parsers=["pdf"],
        formats=["markdown"]
        )

    if not web_content:
        return "Could not extract content from the website."
    
    #Use the Gemini 2.5 Flash model to generate a concise summary of the website content. The prompt should instruct the model to focus on the main value proposition, key features, and any calls to action. The output should be limited to one sentence and should only return the text without any additional formatting or JSON structure.
    LLM_description = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents="""
            You are an expert researcher. Please provide a concise summary of the following website content.
            
            Focus on the main value proposition, key features, and any calls to action.
                
            {MD}        
                        
            please answer in one sentence and only return the text.  Do not return the entire JSON.

        """.format(MD=web_content)    
    )

    #Return the generated summary text from the model's response. Ensure that only the text content is returned without any additional formatting or JSON structure.
    return LLM_description.candidates[0].content.parts[0].text

#This function takes a target business description as input and finds the best matching URL from a list of URLs and their corresponding descriptions stored in a CSV file. It uses a SQL database to store the data and then generates a dynamic list of URLs and descriptions to compare against the target description using the Gemini 2.5 Flash model. The model is prompted to identify which URL's description is most similar to the target description, and the result is printed as the most similar existing advertiser URL.
def find_best_match_url(target_description):
    
    #Load the CSV file containing URLs and their corresponding descriptions into a pandas DataFrame. The CSV file is expected to have columns for URLs and their AI-derived descriptions. The data is then stored in a SQLite database for querying.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    df_fact = pd.read_csv(os.path.join(script_dir, 'urls.csv'))

    connection = sqlite3.connect(os.path.join(script_dir, 'sql_db.db'))
    df_fact.to_sql('best_aud_match', connection, if_exists='replace')

    #Query the SQLite database to retrieve the URLs and their corresponding AI-derived descriptions. The query groups the results by URL and description to ensure that each URL is associated with its unique description. The results are then stored in a pandas DataFrame for further processing.
    sql_1 = """
        
    SELECT 
    k.domain_nm as URL,
    k.description as webcrawl_company_summary_ai_derived_desc,
    k.best_url_match as best_url_match,
    k.tag_source as tag_source


    FROM best_aud_match k
    where k.tag_source = 1
    group by k.domain_nm, k.description, k.best_url_match

    """

    sql_output = connection.execute(sql_1)
    df_sql_output = pd.DataFrame(sql_output.fetchall())
    df_sql_output.columns = ['URL','webcrawl_company_summary_ai_derived_desc','best_url_match','tag_source']

    #Create a dynamic list of URLs and their corresponding descriptions from the DataFrame. The list is formatted as a string where each URL and its description are separated by a new line and a dash for better readability. This dynamic list will be used in the prompt for the Gemini 2.5 Flash model to compare against the target business description.    
    dynamic_list = "\n- ".join(df_sql_output['URL'].tolist()) + "\n- " + "\n- ".join(df_sql_output['webcrawl_company_summary_ai_derived_desc'].tolist())

    #Use the Gemini 2.5 Flash model to generate a response that identifies which URL's description is most similar to the target business description. The prompt instructs the model to compare the target description against the dynamic list of URLs and their descriptions, and to answer with the most similar URL in one word. The response is then printed as the most similar existing advertiser URL.
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents="""
        Which one of the following URLs represents a company that has a webcrawl_company_summary_ai_derived_desc the is most similar to this business description {URL}?

            {DL}        
                    
            please answer in one word.

        """.format(URL=target_description, DL=dynamic_list)    
    )

    return response.text.strip()

#Look for new URLs in the urls.csv file and if the description is "None", then summarize the website content and update the description in the CSV file. Then, for each URL and its description, find the best matching existing advertiser URL using the find_best_match_url function. The script iterates through each row in the CSV file, checks if the description is "None", and if so, it calls the summarize_website function to generate a new description. Finally, it prints the new description for each URL.
def look_for_new_urls():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'urls.csv')
    df_urls = pd.read_csv(csv_path)
    for index, row in df_urls.iterrows():
        target_url = row['domain_nm']

        desc = str(row['description']).strip().lower()
        if desc in ['none', 'nan', '']:
            new_desc = summarize_website(target_url)
            df_urls.at[index, 'description'] = new_desc
            print(f"Updated {target_url}: {new_desc}")
            df_urls.to_csv(csv_path, index=False)

#Look for URLs in the urls.csv file that lack a best URL match and use find_best_match_url() to find the best match.
def look_for_new_url_matches():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'urls.csv')
    df_urls = pd.read_csv(csv_path)
    for index, row in df_urls.iterrows():
        target_url = row['domain_nm']

        desc = str(row['best_url_match']).strip().lower()
        if desc in ['none', 'nan', '']:
            new_match = find_best_match_url(target_url)
            df_urls.at[index, 'best_url_match'] = new_match
            print(f"Updated {target_url}: {new_match}")
            df_urls.to_csv(csv_path, index=False)
    
    

look_for_new_urls()
look_for_new_url_matches()

#run this line of code to test the llm calsification
#print("Most Similar Existing Advertiser URL: "+find_best_match_url(TD))

