# daily-database-reset-for-vm-deployment
----------------------------------------------------------------------------------------------------------------

- reset_db.py removes all info from the following tables then fills the "deploymentdb" database everyday at 00:00, takes about 45-50 minutes

- To run the program manually, change the time given in line 495:
    schedule.every().day.at("00:00").do(job_daily)
  Then run the python code:
    ./reset_db.py
    
- reset_db.py must be running in a terminal to do its job everyday, please rerun the program in case of any restarts

- To manually run the yml files that list data for individual tables:
    ansible-playbook yml_files/list_cluster.yml -vvv

- Database Structure

  deploymentdb
  |
  | -----filled manually-----
  | -> vcenter
  | -----filled using python functions-----
  | -> folder
  | -> cluster
  | -> host_cluster
  | -> host_dswitch
  | -> vlan
  | -----filled using ansible playbooks-----
  | -> datacenter
  | -> template
  | -----filled using both python functions ansible playbooks-----
  | -> datastorecluster

- Libraries used
  -pyVmomi -> Python library to work with vmware vcenters
  -samples -> Files included in the /samples directory
           -> Used to get unverified sessions from vcenters
  -vmware.vapi.vsphere.client -> Uses the unverified sessions to create clients and connect to vcenters
  -ssl
  -yaml
  -re
  -time
  -datetime
  -os
  -pymysql
  -schedule

- counter variables are set to 0 at the start of each run, printing out the total data each corresponding table has
  dc = datacenter
  f = folder
  c = counter
  h = host
  d = dswitch
  v = vlan
  t = template
  dsc = datastore cluster

-  Helper Functions

    - get_vim_objects(content, vim_type):
        Gets data from pyVmomi

    - get_path(entity, current_path=""):
        Helper function for list_template(vcenter, username, password)

    - to_file(obj, filename):
        Helper function for input_to_vars_yml(vcenter, datacenter)
        Outputs the dictionary object passed from input_to_vars_yml() and outputs the data into a yml file in the right format

    - input_to_vars_yml(vcenter, datacenter):
        If the data is pulled using an Ansible Playbook, variables need to be written into a yml file for the corresponding ansible task to use

              ---
              - name: List clusters in a datacenter
              vars_files:
                - vars.yml

        "vars" filename can be changed by the filename parameter of to_file(obj,filename)

              vcenter_hostname: host.local
              vcenter_datacenter: datacenter
              vcenter_username: username
              vcenter_password: password
              vcenter_validate_certs: false
              vcenter_datastore: datastore

        vars.yml has a fixed format. To change the order or variable names, "vars_dict" variable in input_to_vars_yml function can be altered

- Functions

  list_folder():
      Runs the list_folder.yml file, and reads the ansible.log log file to get folder paths that are under the /vm/ folder
      Since virtual machines are stored under the /vm/ folder

  list_cluster():
      Runs the list_cluster.yml file and the reads the output through the log file, which only has the cluster names
  
  list_template(vcenter, username, password):
      Uses pyVmomi library to get all the VM templates, then returns the ones that are under the folder named "RedLaunch"

  list_datastorecluster(vcenter, username, password):
      Uses pyVmomi library to get all datastoreclusters under a vcenter along with some limited info. The free spaces for each datastorecluster is found this way
      Uses the same library to get all clusters under the same vcenter, and the datastores each cluster has
      For every cluster, checks the datastores for their name. If they have any variation of the word "local" in their name, it skips those datastores to save time
      The function also checks the last 2 characters for each datastore, and if the datastore name matches with the one before that, that datastore is skipped as well. This also is done to save time

        SomeDifferentDatastore05
        SomeDatastore01
        SomeDatastore02
        .
        .
        .
        SomeDatastore17

        -SomeDatastore01 is being processed
        -The last two characters are removed -> SomeDatastore
        -Is it the same as the previous datastore?
          SomeDatastore =?= SomeDifferentDatastore
        -They are not the same, so SomeDatastore01 will continue being processed

        -SomeDatastore02 is being processed
        -The last two characters are removed -> SomeDatastore
        -Is it the same as the previous datastore?
          SomeDatastore =?= SomeDatastore
        -SomeDatastore01 and SomeDatastore02 are the same if we remove the last 2 characters
        -SomeDatastore02 will be skipped

      Function runs the list_datastorecluster.yml file to get information about this datastore
      The log file has the datastorecluster this datastore is located in
      Datastorecluster is inserted into the datastorecluster table

  list_host(vcenter):
      Runs the list_host.yml file
      Gets each host a vcenter has, and puts them into the host_cluster table in the database

  list_dswitch(vcenter):
      Runs the list_dswitch.yml file
      Gets each dswitch a vcenter has, and puts them into the host_dswitch table in the database

  list_vlan(vcenter):
      Runs the list_vlan.yml file
      Gets each vlan a vcenter has, and puts them into the vlan table in the database, along with the vlan id

  job_daily():
      This job is scheduled to run at 00:00 every day
      It first removes all information from all tables except for vcenter
      Sets the global variables to 0
      Goes through each vcenter in the vcenter table

      -datastorecluster table is filled
      -datacenter table is filled
      -folder table is filled
      -cluster table is filled
      -host_cluster table is filled
      -host_dswitch table is filled
      -vlan table is filled
      -template table is filled

      Global variables are printed to the screen

----------------------------------------------------------------------------------------------------------------
