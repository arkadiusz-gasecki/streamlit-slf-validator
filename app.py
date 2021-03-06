import streamlit as st
import pandas as pd
import SessionState
import requests, json
import io, base64, csv

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
	params = ['name', 'label', 'type', 'length', 'createable', 'updateable', 'referenceTo' ,'picklistValues','filteredLookupInfo','nillable','defaultedOnCreate']
	params.sort()
	lst = list()
	for column in response['fields']:
		lst.append([ translate_arg(k,v) for k,v in column.items() if k in params ])
	df = pd.DataFrame(lst, columns=params)
	return df

def get_validation_rules(env, token, object_name):
	request_url = st.secrets[env]["url"] + "services/data/v51.0/tooling/query?q=Select Id,Active,Description,ErrorDisplayField,ErrorMessage From ValidationRule Where EntityDefinition.DeveloperName = '"+object_name+"' AND Active=TRUE"
	header = {
		'Authorization': 'Bearer '+token
	}	
	obj_metadata_response = requests.get(request_url, headers=header)
	response = json.loads(obj_metadata_response.text)

	params = ['Id', 'Active', 'Description', 'ErrorDisplayField', 'ErrorMessage' ]
	
	lst = list()
	for column in response['records']:
		lst.append([ translate_arg(k,v) for k,v in column.items() if k in params ])
	df = pd.DataFrame(lst, columns=params)
	return df

def get_flows(env, token, object_name):
	request_url = st.secrets[env]["url"] + "services/data/v51.0/tooling/query?q=SELECT Id, processType, description, status FROM Flow"

	header = {
		'Authorization': 'Bearer '+token
	}	
	obj_metadata_response = requests.get(request_url, headers=header)
	response = json.loads(obj_metadata_response.text)

	lst = list()
	for entry in response['records']:
		if entry['Status'] == 'Active':
			lst.append([entry['Id'], entry['ProcessType'], entry['Status'], entry['Description']])
	df = pd.DataFrame(lst, columns=['Id','ProcessType','Status','Description'])
	return df

def color_nan(x):
	if isinstance(x,list):
		return 'color: black'
	elif pd.isnull(x):
		return 'color: red; font-weight: bold; font-style: italic'
	elif x == False and isinstance(x,bool):
		return 'color: red; font-weight: bold; font-style: italic'
	return 'color: black'

def main_format(x):
	return 'font-size: 12pt; min-width: 100px'
		
def compare_lists(src_list, tgt_list):
	if isinstance(src_list,list) and isinstance(tgt_list,list):
		for elem in src_list:
			if elem not in tgt_list:
				return False		
		return True
	else:
		return None

def get_table_download_link_csv(df,filename):
    csv_file = df.to_csv(sep=';',quoting = csv.QUOTE_ALL, quotechar='"').encode()
    b64 = base64.b64encode(csv_file).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="'+filename+'.csv" target="_blank">Download csv file</a>'
    return href

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
related_object = '' if session_state.sheet_selected is None else session_state.sheet_selected.split('-')[0].strip()
related_object = 'AccountContactRelation' if related_object == 'Acc' else related_object
object_name = st.sidebar.text_input('Salesforce object name', related_object)

if obj:
	df = read_rule_sheet(rule, session_state.sheet_names[0] if session_state.sheet_selected is None else session_state.sheet_selected)
	df.fillna('',inplace=True)
	#st.markdown('Overall:')
	#df

	#st.markdown('Rows to omit:')
	#df[df.iloc[:,0].str.contains('ignore') | df.iloc[:,0].eq('Out of Scope') | df.iloc[:,0].eq('No')]

	st.markdown('Rows for verification:')
	df = df[~(df.iloc[:,0].str.contains('ignore') | df.iloc[:,0].eq('Out of Scope') | df.iloc[:,0].eq('No'))]
	df = df[~(df.iloc[:,5].str.contains('Will be provided') | df.iloc[:,5].eq(' '))]
	if st.checkbox('Show raw data',value=True):
		# for some reason styling does not want to work anymore
		# st.dataframe(df.style.applymap(main_format))
		st.dataframe(df)
#Salesforce Field-API Sunrise Org (2,3)
#Saleforce Field - API UPC Org (5,6)


### -- selector for environments -- ###
st.sidebar.markdown('#')
src_env = st.sidebar.selectbox('Source environment',('UAT','UPRD'))
tgt_env = st.sidebar.selectbox('Target environment',('D6','MIG1','SPRD'))

### -- password for connection ###
passwd = st.sidebar.text_input('Password',type='password',key='50')

### -- part to trigger checking of structures -- ###
st.markdown('#')
col1,col2,col3 = st.beta_columns([1,1,1])

if col2.button('Run check') and passwd == st.secrets['password']:
	st.write('Running check')

	# prepare expected struct
	expect = df.iloc[:,[2,3,5,6]]
	expect.columns = ['Target API Name','Target API Type','Source API Name','Source API Type']

	# connect to source org
	token = login(src_env)
	src_struct = get_object_info(src_env, token, object_name)
	logout(src_env, token)


	# connect to target org
	token = login(tgt_env)
	tgt_struct = get_object_info(tgt_env, token, object_name)
	tgt_validation_rules = get_validation_rules(tgt_env, token, object_name)
	tgt_flows = get_flows(tgt_env, token, object_name)
	logout(tgt_env, token)

	# prepare output
	expect = expect.merge(src_struct,how='left',left_on='Source API Name',right_on='name')
	tmp_expect = expect.copy()
	expect = expect.merge(tgt_struct,how='left',left_on='Target API Name',right_on='name',suffixes=('_src','_tgt'))

	tmp_expect = tmp_expect.merge(tgt_struct, how='right',left_on='Target API Name', right_on='name', suffixes=('_src','_tgt'))
	tmp_expect = tmp_expect[tmp_expect['nillable_tgt'].eq(False) & tmp_expect['defaultedOnCreate_tgt'].eq(False) & tmp_expect['Target API Name'].isnull()]
	tmp_expect = tmp_expect.reindex(columns=['name_tgt','label_tgt','type_tgt', 'nillable_tgt', 'defaultedOnCreate_tgt'])

	# do comparisons
	expect['Picklists Same'] = expect.apply(lambda row: compare_lists(row['picklistValues_src'],row['picklistValues_tgt']), axis=1)
	expect['Types Same'] = expect.apply(lambda row: row['type_src'] == row['type_tgt'], axis=1)
	expect['Lengths Same'] = expect.apply(lambda row: row['length_src'] == row['length_tgt'], axis=1)

	# rearrange columns
	expect = expect.reindex(columns=['Target API Name','Target API Type','Source API Name','Source API Type','name_src','label_src','name_tgt','label_tgt','createable_src','createable_tgt','updateable_src','updateable_tgt','referenceTo_src','referenceTo_tgt','type_src','type_tgt','Types Same','length_src','length_tgt','Lengths Same','picklistValues_src','picklistValues_tgt','Picklists Same','filteredLookupInfo_tgt'])
	
	# for some reason styling does not want to work anymore
	#st.dataframe(expect.style.applymap(color_nan).applymap(main_format), height=800)
	st.table(expect)
	st.markdown(get_table_download_link_csv(expect,object_name), unsafe_allow_html=True)

	#display other required fields
	st.markdown('### Required non default fields missing in specification')
	# for some reason styling does not want to work anymore
	#st.table(tmp_expect.style.applymap(main_format))
	st.table(tmp_expect)

	# display validation rules
	st.markdown('### Validation rules for target object')
	# for some reason styling does not want to work anymore
	#st.table(tgt_validation_rules.style.applymap(main_format))
	st.table(tgt_validation_rules)

	#display flows
	st.markdown("### Flows")
	# for some reason styling does not want to work anymore
	#st.table(tgt_flows.style.applymap(main_format))
	st.table(tgt_flows)


