import streamlit as st

from google import genai

from google.genai import types

from google.genai import Client

from PIL import Image

import os







st.title('image chatbot')

#input_chat = st.selectbox('Ask your question here)

# file uploader for adding image file

input_image = st.file_uploader("Choose an image file", type=['png', 'jpg', 'jpeg'])

# Text area for user input

input_text = st.text_area('Please paste the text here', height = 100).lower()



api_from_streamlite = st.secrets["GEMINI_KEY"]



# google gemini api using streamlit secrets

client = Client(api_key=api_from_streamlite)



chat = client.chats.create(model="gemini-2.0-flash")







# Process inputs on button click (chatgpt)

if st.button("Analyze"):

  try:

    response_text = ""



    if input_image and input_text:

      try:

        image =  Image.open(input_image)



        # response from chatbot

        response = client.models.generate_content(

        model="gemini-2.5-flash", contents=[image, input_text],

        config=types.GenerateContentConfig(

            temperature=0.1

          ),

        )



        # Handle streaming or non-streaming response

        if hasattr(response, '__iter__') and not hasattr(response, 'text'):

          response_text = "".join([part.text for part in response if hasattr(part, 'text')])

        else:

          response_text = response.text if hasattr(response, 'text') else ""

          # Clean up unwanted strings (e.g., 'role - user', 'role - model')

          response_text = response_text.replace('role - user', '').replace('role - model', '').strip()

          st.markdown(response_text, unsafe_allow_html=True)

      except Exception as e:

        st.error(f"Error processing image: {e}")



    else:

      if input_text != 'stop':

        response = chat.send_message_stream(input_text)

        response_text = "".join([part.text for part in response if hasattr(part, 'text')])

        # Clean up unwanted strings (e.g., 'role - user', 'role - model')

        response_text = response_text.replace('role - user', '').replace('role - model', '').strip()        

        st.markdown(response_text, unsafe_allow_html=True)

      else:

        print('Thank you for your conversation. Have a nice day!')



  except Exception as e:

      st.write(f"Error: {e}")
