import streamlit as st
import pandas as pd
import SessionState
import requests, json

### set up page settings
st.set_page_config(page_title="File uploader", layout="wide", initial_sidebar_state="expanded")

### --- define session state values --- ###
session_state = SessionState.get(sheet_names=list(), sheet_selected=None)


#########################  functions ################################

def read_rule_sheet(rule, sheet_name):
	df = pd.read_excel(rule, engine='openpyxl',skiprows=2,usecols='A:G',sheet_name=sheet_name)
	return df

def login(env):
	
	request_url = st.secrets[env]["url"]+'services/oauth2/token'
	body = {
		'grant_type': 'password'
	  , 'client_id': st.secrets[env]['client_id']
	  , 'client_secret': st.secrets[env]['client_secret']
	  , 'username': st.secrets[env]['username']
	  , 'password': st.secrets[env]['password']+st.secrets[env]['token']
	}

	login_response = requests.request("POST", request_url, data=body)
	if login_response.status_code != 200:
		st.write("Error "+str(login_response.status_code))
		st.write(json.loads(login_response.text))
		return None
	else:
		st.write("Login to %s successful" % env)
		response = json.loads(login_response.text)
		return response['access_token']

def logout(env, token):
				
	# prepare logout statement
	request_url = st.secrets[env]["url"]+'services/oauth2/revoke'
	body = {
   		'token': token
	}
	# make logout request
	logout_response = requests.post(request_url, data=body)
	if logout_response.status_code != 200:
		st.write("Error "+str(logout_response.status_code))
		st.write(json.loads(logout_response.text))
	else:
		st.write("Logout from %s successful" % env)

def translate_arg(k,v):
	if k == 'picklistValues':
		return [elem['value'] for elem in v]
	elif k == 'referenceTo':
		return v[0] if len(v) > 0 else ''
	else:
		return v

def get_object_info(env, token, object_name):
	# get metadata info about desired object

	request_url = st.secrets[env]["url"] + 'services/data/v51.0/sobjects/'+object_name+'/describe'
	header = {
		'Authorization': 'Bearer '+token
	}	
	obj_metadata_response = requests.get(request_url, headers=header)
	response = json.loads(obj_metadata_response.text)
	
	#parse response about object
	params = ['name', 'label', 'type', 'length', 'createable', 'updateable', 'referenceTo' ,'picklistValues']
	params.sort()
	lst = list()
	for column in response['fields']:
		lst.append([ translate_arg(k,v) for k,v in column.items() if k in params ])
	df = pd.DataFrame(lst, columns=params)
	return df



#########################  main content ################################

### --- define section to upload xls file --- ###
st.markdown('### Rules file')
rule = st.file_uploader("Upload excel file with rules", type=['xlsx'], key='1')

if not rule:
	st.write("Upload .xlsx file with rules definition")
else:
	xls = pd.ExcelFile(rule)
	### take only sheets that have 'Fields' in name
	session_state.sheet_names = [ n for n in xls.sheet_names if 'Fields' in n ]


### -- add sheet selector in sidebar --- ###

if not isinstance(session_state.sheet_names,list):
	obj = st.sidebar.empty()
else:
	obj = st.sidebar.selectbox('Select object', session_state.sheet_names)
	session_state.sheet_selected = obj

### -- add mapper to proper object name --- ###
object_name = st.sidebar.text_input('Salesforce object name', '' if session_state.sheet_selected is None else session_state.sheet_selected.split('-')[0].strip())

if obj:
	df = read_rule_sheet(rule, session_state.sheet_names[0] if session_state.sheet_selected is None else session_state.sheet_selected)
	df.fillna('',inplace=True)
	#st.markdown('Overall:')
	#df

	#st.markdown('Rows to omit:')
	#df[df.iloc[:,0].str.contains('ignore') | df.iloc[:,0].eq('Out of Scope') | df.iloc[:,0].eq('No')]

	st.markdown('Rows for verification:')
	df = df[~(df.iloc[:,0].str.contains('ignore') | df.iloc[:,0].eq('Out of Scope') | df.iloc[:,0].eq('No'))]
	df = df[~df.iloc[:,5].str.contains('Will be provided')]
	df
#Salesforce Field-API Sunrise Org (2,3)
#Saleforce Field - API UPC Org (5,6)


### -- selector for environments -- ###
st.sidebar.markdown('#')
src_env = st.sidebar.selectbox('Source environment',('UAT','UPRD'))
tgt_env = st.sidebar.selectbox('Target environment',('D6','MIG1','SPRD'))

### -- password for connection ###
passwd = st.sidebar.text_input('Password',type='password',key=50)

### -- part to trigger checking of structures -- ###
st.markdown('#')
col1,col2,col3 = st.beta_columns([1,1,1])

if col2.button('Run check') and passwd == st.secrets['password']:
	st.write('Running check')

	# connect to source org
	token = login(src_env)
	src_struct = get_object_info(src_env, token, object_name)

	src_expect = df.iloc[:,[5,6]]
	src_expect.columns = ['API Name','API Type']

	src_expect = src_expect.merge(src_struct,how='left',left_on='API Name',right_on='name')
	src_expect

	logout(src_env, token)


	# connect to target org
	token = login(tgt_env)
	logout(tgt_env, token)

