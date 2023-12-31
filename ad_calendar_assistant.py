# -*- coding: utf-8 -*-
"""AD Calendar Assistant

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1CDj3RkdW2FruFKlJf3_cyvXIlIGFUJGh

# Sample Colab for Extracting Data from OCRed PDFs Using Regex and LLMs

One can use this notebook to build a pipeline to parse and extract data from OCRed PDF files. _**Warning:** When using LLMs for entity extraction, be sure to perform extensive quality control. They are very susceptible to distracting language (latching on to text that sound "kind of like" what you're looking for) and missing language (making up content to fill any holes), and importantly, they do **NOT** provide any hints to when they may be erroring. You need to make sure random audits are part of your workflow!_ Below we've worked out a workflow using regular expressions and LLMs to parse data from zoning board orders, but the process is generalizable.

1. Collect a set of PDFs
2. Place OCRed PDFs into the a folder
3. Write regular expressions to pull out data
4. Write LLM prompts to pull out data

# Load Libraries


First we load the libraries we need. Note, if you try to run the cell, and you get something like `ModuleNotFoundError: No module named 'mod_name'`, you'll need to install the module. You can do this commentating the line below that reads `#!pip install mod_name` if it's listed. If it isn't, you can probably install it with a similarly formatted command.
"""

#!pip install os
!pip install PyPDF2
#!pip install re
#!pip install pandas
#!pip install numpy

!pip install transformers
!pip install openai==0.28
!pip install tiktoken
!pip install ics

import os
from os import walk, path
import PyPDF2
import re
import pandas as pd
import numpy as np
import random

def read_pdf(file):
    try:
        pdfFile = PyPDF2.PdfReader(open(file, "rb"), strict=False)
        text = ""
        for page in pdfFile.pages:
            text += " " + page.extract_text()
        return text
    except:
        return ""

# Test Audio call
# Only works on Mac. If you aren't using a Mac, you should disable such calls below.
#tmp = os.system( "say Testing, testing, one, two, three.")
#del(tmp)

import json

from nltk.tokenize import word_tokenize, sent_tokenize

import openai
from transformers import GPT2TokenizerFast
tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

import tiktoken
ENCODING = "gpt2"
encoding = tiktoken.get_encoding(ENCODING)

def complete_text(prompt,temp=0,trys=0,clean=True):

    global tokens_used

    model="text-davinci-003"
    model_token_limit = 4097

    token_count = len(encoding.encode(prompt))
    max_tokens=2000# model_token_limit-round(token_count+5)

    #try:
    response = openai.Completion.create(
      model=model,
      prompt=prompt,
      temperature=temp,
      max_tokens=max_tokens,
      top_p=1.0,
      frequency_penalty=0.0,
      presence_penalty=0.0
    )
    output = str(response["choices"][0]["text"].strip())
    #except:
    #    print("Problem with API call!")
    #    output = """{"output":"error"}"""

    tokens_used += token_count+len(encoding.encode(output))

    if clean:
        return clean_pseudo_json(output,temp=0,trys=trys)
    else:
        return output

def clean_pseudo_json(string,temp=0,key="output",trys=0,ask_for_help=1):
    try:
        output = json.loads(string)[key]
    except:
        try:
            string_4_json = re.findall("\{.*\}",re.sub("\n","",string))[0]
            output = json.loads(string_4_json)[key]
        except:
            try:
                string = "{"+string+"}"
                string_4_json = re.findall("\{.*\}",re.sub("\n","",string))[0]
                output = json.loads(string_4_json)[key]
            except Exception as e:
                prompt = "I tried to parse some json and got this error, '{}'. This was the would-be json.\n\n{}\n\nReformat it to fix the error.".format(e,string)
                if trys <= 3:
                    if trys == 0:
                        warm_up = 0
                    else:
                        warm_up = 0.25
                    output = complete_text(prompt,temp=0+warm_up,trys=trys+1)
                    print("\n"+str(output)+"\n")
                elif ask_for_help==1:
                    print(prompt+"\nReformaing FAILED!!!")
                    #try:
                    #    os.system( "say hey! I need some help. A little help please?")
                    #except:
                    #    print("'say' not supported.\n\n")
                    output = input("Let's see if we can avoid being derailed. Examine the above output and construct your own output text. Then enter it below. If the output needs to be something other than a string, e.g., a list or json, start it with `EVAL: `. If you're typing that, be very sure there's no malicious code in the output.\n")
                    if output[:6]=="EVAL: ":
                        output = eval(output[6:])
                else:
                    output = "There was an error getting a reponse!"

    return output

"""# Input OpenAI API Key & LLM settings

You'll need an API key to use an LLM. After creating an OpenAI account, you can create an API key here: https://platform.openai.com/account/api-keys

Enter your key between the quation marks next to `openai.api_key =` below, and run that cell.
"""

# Toggle LLM usage on or off
use_LLM = True

llm_temperature = 0 # I strongly suggest keeping the LLM's temp at zero to avoid it making things up.

openai.api_key = "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" # <<--- REPLACE WITH YOUR KEY

"""# Load and pase files
Next, place a bunch of OCRed pdf files in the right folder (here, the `/content/gdrive/entity_extraction_sample_data/boston/` folder). FWIW, you can use Adobe Pro to OCR in batch. Note: to make your files visisble at a location like that above, you'll need to add them to your Google Drive. E.g., you would need to copy https://drive.google.com/drive/folders/1H3bMgxzNxwxNL2YK6eMWt3nX985oBqVS?usp=sharing to your GDrive and name it `entity_extraction_sample_data` for it to be accessable at `/content/gdrive/entity_extraction_sample_data/`.
"""

# this mounts your google drive
from google.colab import drive
drive.mount('/content/gdrive')

df = pd.DataFrame() #this will create an empty dataframe

# list the files in the drive
filepath = "/content/gdrive/MyDrive/syllabus/" # this is where we'll be looking for files
f = []
for (dirpath, dirnames, filenames) in walk(filepath): # create a list of file names
    f.extend(filenames)
    break

f #show list

sample = 1
# #sample = len(f) #if you want to go through all the files, uncomment this line and comment out the above



temp_calendar = {}

token_counts = []
for file in random.choices(f,k=sample): # for each file in the list of file names, do some stuff

    tokens_used = 0

    column_names = ["file"]
    column_values = [file]

    fileloc = filepath+file
    txt = read_pdf(fileloc)
    text = open(fileloc, 'r').read()
    #print("text here: ", text)
    words = len(text.split())

    print("Parsing ~{} words ({} tokens) from: \"{}\"\n".format(words,len(encoding.encode(text)),fileloc))

    try:
      # ---------------------------------------------------------
      # time
      # ---------------------------------------------------------
      time = re.search("(([0-2]?)((([0-9]+)(:+)([0-5]+)([0-9]+))+)(\s?)(([AaPp][Mm])?))",text, flags=re.IGNORECASE).groups(0)[0].strip()
      column_names.append("time")
      column_values.append(time)
    except:
      column_names.append("time")
      column_values.append("all day")


    if use_LLM:

        #try:
        # ---------------------------------------------------------
        # class name
        # ---------------------------------------------------------
        prompt_text = """Below you will be provided with syllabi from professors so you know which assignments are due on each date. You're looking to find the _class name_. That is, the name of the class found at the top of the syllabus.

    Here's the text of the class name.

    {}

    ---

    Return a json object, including the outermost currly brakets, where the key is "output" and the value is a the _class name_. If you can't find a _class name_ in the text of the above, answer "none found". Be sure to use valid json, encasing keys and values in double quotes, and escaping internal quotes and special characters as needed.""". format(text)
        #print(prompt_text)
        class_name = complete_text(prompt_text,temp=llm_temperature)
        column_names.append("class_name")
        column_values.append(class_name)
      #except:
        #column_names.append("class_name")
        #column_values.append("NA")

      #try:
        # ---------------------------------------------------------
        # assignment
        # ---------------------------------------------------------
        prompt_text = """Below you will be provided with part of a syllabus including a list of homework assignments and their due dates.

    Here's the text:

    {}

    ---

    Return a json object, including the outermost currly brakets, where the key is "output" and the value is a list of the assignments. Each assignment is a json object where the "key" is its "date" and the "value" is a description of the assignment. Make the date in the format 2023-MONTH-DAY. If you can't find any assignments in the text of the above, return an empty list. Be sure to use valid json, encasing keys and values in double quotes, and escaping internal quotes and special characters as needed.""". format(text)
        #print(prompt_text)
        assignment = complete_text(prompt_text,temp=llm_temperature)
        column_names.append("assignment")
        column_values.append(assignment)
        temp_calendar[class_name] = assignment

        #date = complete_text(prompt_text,temp=llm_temperature)
        #column_names.append("date")
        #column_values.append(date)


    #############################################################

    # After testing or when working with large numbers, you may want to comment this next bit out

    # Show your work
    i = 0
    for datum in column_values:
        print("{}: {}\n".format(column_names[i].upper(),datum))
        i+=1


    # Show cost per run
    if use_LLM:
        print("Tokens used (approx.): {} (API Cost ~${})\n".format(tokens_used,tokens_used*(0.002/1000))) # See https://openai.com/pricing
        token_counts.append(tokens_used)

    print("================================================\n")

    df = pd.concat([df,pd.DataFrame([column_values],columns=column_names)], ignore_index=True,sort=False)

print("Average approx. tokens used per item {} (API Cost ~${})\n".format(np.array(token_counts).mean(),np.array(token_counts).mean()*(0.002/1000))) # See https://openai.com/pricing

display(df)

temp_calendar

def to_ics_start(date):
  date = re.sub("-", "", date)
  date = date+"T00000"
  return date

#to_ics_start("2023-09-18")

def to_ics_end(date):
  date = re.sub("-", "", date)
  date = date+"T23590"
  return date

import uuid
import random

myuuid = uuid.uuid4()

rd = random.Random()
rd.seed(0)
uuid.UUID(int=rd.getrandbits(128))

print('Your UUID is: ' + str(myuuid))

ics_file = """BEGIN:VCALENDAR
VERSION:2.0
"""
for item in temp_calendar.keys():
  #print(item)
  for assignment in temp_calendar[item]:
    ics_file+="BEGIN:VEVENT\n"
    ics_file+="PRODID:{}\n".format(class_name)
    ics_file+="UID:{}\n".format(uuid.UUID(int=rd.getrandbits(128)))
    ics_file+="DTSTART:{}\n".format(to_ics_start(list(assignment.keys())[0]))
    ics_file+="DTEND:{}\n".format(to_ics_end(list(assignment.keys())[0]))
    ics_file+="SUMMARY:{}\n".format(assignment[list(assignment.keys())[0]])
    ics_file+="END:VEVENT\n"
    #print(assignment)
ics_file+="END:VCALENDAR\n"
print(ics_file)

#f = open( 'assignment_dates', 'w' )
#f.write( 'ics_file = ' + repr(ics_file) + '\n' )
#f.close()

with open("assignments.ics", "w") as out_file:
    out_file.write(ics_file)

from google.colab import files
files.download("assignments.ics")