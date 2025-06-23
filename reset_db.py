#!/usr/bin/python3.11

from vmware.vapi.vsphere.client import create_vsphere_client
from samples import ssl_helper
from pyVmomi import vim
from pyVim import connect
from pyVim.connect import SmartConnect, Disconnect
import ssl
import yaml
import re
import time
from datetime import datetime
import os
import pymysql
import schedule
import warnings
warnings.filterwarnings("ignore")

username="username"
password="password"

#counter variables
dc = 0
f = 0
c = 0
h = 0
d = 0
v = 0
t = 0
dsc = 0

session = ssl_helper.get_unverified_session()

context = ssl.SSLContext()
context.verify_mode = ssl.CERT_NONE
 
def get_vim_objects(content, vim_type):
  container = content.viewManager.CreateContainerView(content.rootFolder, [vim_type], True)
  return container.view

def get_path(entity, current_path=""):
  if isinstance(entity.parent, vim.Folder):
    current_path = get_path(entity.parent, current_path)
  if isinstance(entity, vim.Folder) or isinstance(entity, vim.VirtualMachine):
    current_path += f"/{entity.name}"
  return current_path
            
def to_file(obj, filename):
  with open(f'{filename}.yml', 'w',) as f :
    yaml.dump(obj,f,sort_keys=False)
            
def input_to_vars_yml(vcenter, datacenter):

  vars_dict = {
    'vcenter_hostname':vcenter,
    'vcenter_datacenter':datacenter,
    'vcenter_username':username,
    'vcenter_password':password,
    'vcenter_validate_certs':False,
    'vcenter_datastore': datacenter
  }
  
  return to_file(obj=vars_dict, filename='yml_files/vars')

def list_folder(cur, conn):
  log_file = "yml_files/ansible.log"
  f = open(log_file, 'w')
  f.close()
  
  os.system("ANSIBLE_LOCALHOST_WARNING=false ansible-playbook ../reset_database/yml_files/list_folder.yml >yml_files/ansible.log")
  
  folder_list = []
  
  with open(log_file, 'r') as f:
    for line in f:
      match = re.search(r'"msg": "(.*)"', line)
      if match and "/vm/" in line:
        folder_list.append(match.group(1).strip())
        
  f.close()
        
  return folder_list
  
def list_cluster(cur, conn):
  log_file = "yml_files/ansible.log"
  f = open(log_file, 'w')
  f.close()
  
  os.system("ANSIBLE_LOCALHOST_WARNING=false ansible-playbook ../reset_database/yml_files/list_cluster.yml >yml_files/ansible.log")
  
  cluster_list = []
  
  with open(log_file, 'r') as f:
    for line in f:
      match = re.search(r'"msg": "(.*)"', line)
      if match:
        cluster_list.append(match.group(1).strip())
        
  f.close()
  return cluster_list
 
def list_template(cur, conn, vcenter, datacenter, content):
    
 
    template_names = []
    for vm in get_vim_objects(content, vim.VirtualMachine):
        if vm.config.template:
            template_names.append(vm.name)
  
    return template_names

def list_datastorecluster(cur, conn, vcenter, content):

  datastore_clusters = get_vim_objects(content, vim.StoragePod)
  drs_cluster = {}

  for drs in datastore_clusters:
    drs_cluster[drs.summary.name] = drs.summary.freeSpace

  clusters = get_vim_objects(content, vim.ClusterComputeResource)

  log_file = "ansible.log"

  global dsc
  
  for cluster in clusters:
    checklist = []
    dtstr = ' '

    if len(cluster.datastore) != 0:
      for datastore in cluster.datastore:
        if "LOCAL" or "local" or "Local" not in datastore.name:
          if dtstr[:-2] != datastore.name[:-2]:
            f = open(log_file, 'w')
            f.close()

            input_to_vars_yml(vcenter, datastore.name)
            os.system("ANSIBLE_LOCALHOST_WARNING=false ansible-playbook ../reset_database/yml_files/list_datastorecluster.yml >ansible.log")

            with open(log_file, 'r') as f:
              for line in f:
                match = re.search(r'"msg": "(.*)"', line)
                if match:
                  drs = match.group(1).strip()
                  check = drs + ' ' + cluster.name
                  cur.execute("""SELECT EXISTS(
                                  SELECT 1
                                  FROM datastorecluster
                                  WHERE datastoreClusterName = %s AND clusterName = %s AND vcenterName = %s)
                                  """, (drs, cluster.name, vcenter))
                  exists = cur.fetchone()[0]

                  if not exists and drs != "N/A":
                    for clu in datastore_clusters:
                      if clu.summary.name == drs:
                        freeSpace = clu.summary.freeSpace
                        checklist.append(check)
                        dsc += 1
                        cur.execute("""INSERT INTO datastorecluster (datastoreClusterName, clusterName, freeSpace, vcenterName) 
                                        VALUES (%s, %s, %s, %s)
                                        """, (drs, cluster.name, freeSpace/(1024**4), vcenter))
                        conn.commit()
            f.close()
        dtstr = datastore.name         

def list_host(cur, conn, vcenter):
  log_file = "yml_files/ansible.log"
  f = open(log_file, 'w')
  f.close()
  
  os.system("ANSIBLE_LOCALHOST_WARNING=false ansible-playbook ../reset_database/yml_files/list_host.yml >yml_files/ansible.log")
  
  global h
  
  with open(log_file, 'r') as f:
    for line in f:
      match = re.search(r'"Cluster: (.*)"', line)
      if match:
        cluster = match.group(1).strip()
      
      match = re.search(r'"Hosts: \[(.*)\]"', line)
      if match:
        matches = re.findall(r"'(.*?)'", match.group(1).strip())
        for host in matches:
            cur.execute("""SELECT EXISTS(
                              SELECT 1
                              FROM host_cluster
                              WHERE clusterName = %s AND hostName = %s AND vcenterName = %s
                              )""", (cluster, host, vcenter))
            exists = cur.fetchone()[0]
              
            if not exists:
              h += 1
              cur.execute("""INSERT INTO host_cluster (clusterName, hostName, vcenterName) 
                                VALUES (%s, %s, %s)
                                """, (cluster, host, vcenter))
              conn.commit()
  f.close()
  
def list_dswitch(cur, conn, vcenter):
  log_file = "yml_files/ansible.log"
  f = open(log_file, 'w')
  f.close()
  
  os.system("ANSIBLE_LOCALHOST_WARNING=false ansible-playbook ../reset_database/yml_files/list_dswitch.yml >yml_files/ansible.log")
  
  global d
  
  with open(log_file, 'r') as f:
    for line in f:
      match = re.search(r'"hosts": \[', line)
      if match:
        check = False
        hosts = []
        while not check:
          match = re.search(r'"name": "(.*)",', line)
          if match:
            for host in hosts:
                cur.execute("""SELECT EXISTS(
                                  SELECT 1
                                  FROM host_dswitch
                                  WHERE dswitchName = %s AND hostName = %s AND vcenterName = %s)
                                  """, (match.group(1).strip(), host, vcenter))
                exists = cur.fetchone()[0]
                
                if not exists:
                    d += 1
                    cur.execute("""INSERT INTO host_dswitch (dswitchName, hostName, vcenterName) 
                                      VALUES (%s, %s, %s)
                                      """, (match.group(1).strip(), host, vcenter))
                    conn.commit()
          else:
            host = re.search(r'"(.*)",', line)
            if host:
              hosts.append(host.group(1).strip())
          line = next(f)
          check = re.search(r'"settings": ', line)
        
  f.close()
  
def list_vlan(cur, conn, vcenter):
  log_file = "yml_files/ansible.log"
  f = open(log_file, 'w')
  f.close()
  
  os.system("ANSIBLE_LOCALHOST_WARNING=false ansible-playbook ../reset_database/yml_files/list_vlan.yml >yml_files/ansible.log")
  
  global v
  
  with open(log_file, 'r') as f:
    for line in f:
      match = re.search(r'"dvswitch": "(.*)",', line)
      if match:
        line = next(f)
        vlan = re.search(r'"name": "(.*)",', line)
        if vlan:
          line = next(f)
          line = next(f)
          
          trunk = re.search(r'"trunk": false,', line)
          if trunk:
            line = next(f)

            vlan_id = re.search(r'"vlan_id": "(.*)"', line)
            if vlan_id:
                cur.execute("""SELECT EXISTS(
                                  SELECT 1
                                  FROM vlan
                                  WHERE vlanName = %s AND vlanID = %s AND dswitchName = %s AND vcenterName = %s)
                                  """, (vlan.group(1).strip(), vlan_id.group(1).strip(), match.group(1).strip(), vcenter))
                
                exists = cur.fetchone()[0]
                
                if not exists:
                    v += 1
                    cur.execute("""INSERT INTO vlan (vlanName, vlanID, dswitchName, vcenterName) 
                                      VALUES (%s, %s, %s, %s)
                                      """, (vlan.group(1).strip(), vlan_id.group(1).strip(), match.group(1).strip(), vcenter))
                    conn.commit()
  f.close()

def job_daily():
  print()
  print("DATABASE RESET STARTED - ", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
  print()
  print()
  
  conn = pymysql.connect( 
    host='host', 
    user='username',  
    password = "password", 
    db='database_name', 
  ) 
  
  cur = conn.cursor()

  cur.execute("SELECT vcenterName FROM vcenter") 
  output = cur.fetchall() 
  vcenters = []
        
  for i in output: 
    vcenters.append(i[0])
  
  cur.execute("""DELETE FROM datacenter""")
  conn.commit()
  cur.execute("""DELETE FROM folder""")
  conn.commit()
  cur.execute("""DELETE FROM cluster""")
  conn.commit()
  cur.execute("""DELETE FROM host_cluster""")
  conn.commit()
  cur.execute("""DELETE FROM host_dswitch""")
  conn.commit()
  cur.execute("""DELETE FROM vlan""")
  conn.commit()
  cur.execute("""DELETE FROM template""")
  conn.commit()
  cur.execute("""DELETE FROM datastorecluster""")
  conn.commit()
  
  #counter variables
  global dc
  global f
  global c
  global h
  global d
  global v
  global t
  global dsc
  
  dc = 0
  f = 0
  c = 0
  h = 0
  d = 0
  v = 0
  t = 0
  dsc = 0

  client = create_vsphere_client(server=vcenter, username=username, password=password, session=session)
  si = SmartConnect(host=vcenter, user=username, pwd=password, port=443, sslContext=context)
  content = si.RetrieveContent()
                                        
  for vcenter in vcenters:

    list_datastorecluster(cur=cur, conn=conn, vcenter=vcenter, content=content)
    list_of_datacenters = client.vcenter.Datacenter.list()
      
    for datacenter in list_of_datacenters:
          
      for msg in list_template(cur=cur, conn=conn, vcenter=vcenter, datacenter=datacenter, content=content):
        cur.execute("""SELECT EXISTS(
                            SELECT 1
                            FROM template
                            WHERE templateName = %s AND vcenterName = %s)
                            """, (msg, vcenter))
        exists = cur.fetchone()[0]
            
        if not exists:
          t += 1
          cur.execute("""INSERT INTO template (templateName, vcenterName) 
                              VALUES (%s, %s)
                              """, (msg, vcenter))
          conn.commit()
            
        cur.execute("""SELECT EXISTS(
                          SELECT 1
                          FROM datacenter
                          WHERE datacenterName = %s AND vcenterName = %s
                          )""", (datacenter.name, vcenter))
        exists = cur.fetchone()[0]
        if not exists:
          dc += 1
          cur.execute("""INSERT INTO datacenter (datacenterName, vcenterName)
                            VALUES (%s, %s)
                            """, (datacenter.name, vcenter))
          conn.commit()
      input_to_vars_yml(vcenter, datacenter.name)
      for msg in list_folder(cur=cur, conn=conn):
        cur.execute("""SELECT EXISTS(
                            SELECT 1
                            FROM folder
                            WHERE folderName = %s AND datacenterName = %s AND vcenterName = %s)
                            """, (msg, datacenter.name, vcenter))
        exists = cur.fetchone()[0]
        if not exists:
          f += 1
          cur.execute("""INSERT INTO folder (folderName, datacenterName, vcenterName) 
                              VALUES (%s, %s, %s)
                              """, (msg, datacenter.name, vcenter))
          conn.commit()
      for msg in list_cluster(cur=cur, conn=conn):
        cur.execute("""SELECT EXISTS(
                            SELECT 1
                            FROM cluster
                            WHERE clusterName = %s AND datacenterName = %s AND vcenterName = %s)
                            """, (msg, datacenter.name, vcenter))
        exists = cur.fetchone()[0]
        if not exists:
          c += 1
          cur.execute("""
            INSERT INTO cluster (clusterName, datacenterName, vcenterName) 
            VALUES (%s, %s, %s)
            """, (msg, datacenter.name, vcenter))
          conn.commit()
      list_host(cur=cur, conn=conn, vcenter=vcenter)
      list_dswitch(cur=cur, conn=conn, vcenter=vcenter)
      list_vlan(cur=cur, conn=conn, vcenter=vcenter)

  print('Datacenter count: ', dc)
  print('Folder count: ', f)
  print('Cluster count: ', c)
  print('Host count: ', h)
  print('Dswitch count: ', d)
  print('Vlan count: ', v)
  print('Template count: ', t)
  print('Datastore cluster count: ', dsc)
      
  conn.close()
  Disconnect(si)
  
  print("\n\nDATABASE RESET DONE - \n", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

schedule.every().day.at("00:00").do(job_daily)

while True:
  schedule.run_pending()
  time.sleep(1)
