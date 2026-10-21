# PLacement Predictor - Streamlit app

import streamlit as st
import numpy as np
import pandas as pd
import pickle

#Loading the saved model
with open('models/placement_model.pkl', 'rb') as f:  #opens model file in read binary mode
    model = pickle.load(f)                              #loads our saved model back into memory

st.title("Student Placement Predictor")
st.write("Enter student details below to predict placement chances.")
st.subheader("Student Details")             #smaller heading

#Inputing the fields
col1, col2 = st.columns(2)                  #splits page into 2 columns side by side

with col1:
    gender = st.selectbox("Gender", ["Male", "Female"])         #dropdown menu
    ssc_p = st.slider("10th Percentage", 0.0, 100.0, 60.0)      #sliding number input (min, max, default value)
    hsc_p = st.slider("12th Percentage", 0.0, 100.0, 60.0)
    hsc_s = st.selectbox("12th Stream", ["Commerce", "Science", "Arts"])
    degree_p = st.slider("Degree Percentage", 0.0, 100.0, 60.0)

with col2:
    degree_t = st.selectbox("Degree Type", ["Sci&Tech", "Comm%Mgmt", "Others"])
    workex = st.selectbox("Work Experience", ["Yes", "No"])
    etest_p = st.slider("Employability Test Percent", 0.0, 100.0, 60.0)
    specialisation = st.selectbox("MBA Specialisation", ["Mkt&Fin", "Mkt&HR"])
    mba_p = st.slider("MBA Percentage", 0.0, 100.0, 60.0)

#Adding the buttons
if st.button("Predict Placement"): #creates a clickable button and inside only runs when button is clicked

    #Encoding inputs exactly like we did in feature engineering
    gender_enc = 1 if gender == "Male" else 0
    workex_enc = 1 if workex == "Yes" else 0
    specialisation_enc = 1 if specialisation == "Mkt&Fin" else 0

    hsc_s_Commerce = 1 if hsc_s == "Commerce" else 0
    hsc_s_Science = 1 if hsc_s == "Science" else 0

    degree_t_Others = 1 if degree_t == "Others" else 0
    degree_t_SciTech = 1 if degree_t == "Sci&Tech" else 0


    #Scalling Numerical Values using the same MinMax formula
    ssc_p_scaled = (ssc_p - 40.89) / (89.40 - 40.89)
    hsc_p_scaled = (hsc_p - 37.00) / (97.70 - 37.00)
    degree_p_scaled = (degree_p - 50.00) / (91.00 - 50.00)
    etest_p_scaled = (etest_p - 50.00) / (98.00 - 50.00)
    mba_p_scaled = (mba_p - 51.21) / (77.89 - 51.21)

    # Creating input DataFrame for model
    input_data = pd.DataFrame([[
        gender_enc, ssc_p_scaled, 0, hsc_p_scaled, 0,
        degree_p_scaled, workex_enc, etest_p_scaled,
        specialisation_enc, mba_p_scaled,
        hsc_s_Commerce, hsc_s_Science,
        degree_t_Others, degree_t_SciTech
    ]], columns=['gender', 'ssc_p', 'ssc_b', 'hsc_p', 'hsc_b',
                 'degree_p', 'workex', 'etest_p', 'specialisation',
                 'mba_p', 'hsc_s_Commerce', 'hsc_s_Science',
                 'degree_t_Others', 'degree_t_Sci&Tech'])

    #Making Prediction
    prediction = model.predict(input_data)[0]   #uses our saved model to predict

    #Show Reslut
    st.subheader("Prediction Result")
    if prediction == 1:
        st.success("Student is likely to be PLACED")
    else:
        st.error("Student is likely to be NOT PLACED")






