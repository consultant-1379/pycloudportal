# Set up for install #

`yum install epel-release -y`\
`yum update -y`\
`yum groups mark install "Development Tools"`\
`yum groups mark convert "Development Tools"`\
`yum groupinstall "Development Tools"`\
`yum install httpd-devel httpd mod_wsgi python3-devel openldap-devel redis zlib-devel openssl-devel sqlite-devel -y`\
`systemctl start redis`\
`systemctl enable redis`\
`mkdir -p /var/log/pyvcloud `\
`mkdir -p /srv/isodiskmount/isodir`\


## Disable SELinux ##
<pre>`setenforce 0`     # disable temporarily
https://www.ibm.com/docs/ja/ahts/4.0?topic=t-disabling-selinux # disable permanently
</pre>

## Download & Install sqlite3 ##

<pre> https://number1.co.za/upgrading-sqlite-on-centos-to-3-8-3-or-later/ </pre>
`cd /opt`\
`wget https://www.sqlite.org/2019/sqlite-autoconf-3280000.tar.gz`\
`tar -xzf sqlite-autoconf-3280000.tar.gz`\
`cd sqlite-autoconf-3280000`\
`./configure`\
`make`\
`sudo make install`

## When sqlite is installed, python3 needs to be compiled & installed and pointed to the correct shared libraries ##
### Download Python 3.6 source, extract it and cd into the directory ###
<pre>
Python versions higher than 3.6 may be used, but for centos7 the system openssl will also need to be compiled from source and linked to the python used for the creation of the virtual environment.
Assuming openssl installed to /opt/openssl with ./config --prefix=/opt/openssl && make && make install
LD_RUN_PATH=/usr/local/lib  ./configure --with-openssl=/opt/openssl --enable-shared --enable-optimizations
</pre>
`cd /opt/Python-x.y.z`\
`LD_RUN_PATH=/usr/local/lib  ./configure --enable-shared --enable-optimizations`\
`LD_RUN_PATH=/usr/local/lib make`\
`LD_RUN_PATH=/usr/local/lib make altinstall`\

### make altinstall will not replace the system python but will leave the binary in : ###

<pre> /usr/local/bin/python3.X </pre>

## Use this binary to create the virtualenvironment for the application ##

`/usr/local/bin/python3.X -m venv /opt/venvpycloud`\

### when the virtualenv has been made, source into it ###

`source /opt/venvpycloud/bin/activate`\

### from inside the venv ###

`python -m pip install --upgrade pip`\
`python -m pip install --upgrade setuptools`\
`python -m pip install mod_wsgi`\


## Clone PycloudPortal repo

`cd /opt`\
`git clone https://<signum>@gerrit.ericsson.se/a/OSS/ENM-Parent/SQ-Gate/com.ericsson.ci.cloud/pycloudportal`\


# DJANGO SETUP #
<pre> Make sure you are in the /opt/pycloudportal directory and source into the venvpycloud virtualenvironment </pre>
`pip install -r requirements.txt`\
`python manage.py migrate`\
`python manage.py createsuperuser`\
`python manage.py collectstatic`\
`python manage.py runserver 0.0.0.0:4321`\
	<pre>Open your web browser and navigate to http://<HOSTNAME_OF_SERVER>:4321
	Log in with the superuser account you created earlier, and select ‘SPP ADMIN SECTION’
Select the AuthDetails Table on the left and enter the authentication details for the Vmware Cloud director and the vsphere under the names (‘vcd’ and ‘vsphere’ respectively) </pre>
<pre>
Close the runserver and then run the imports </pre>
`bash -i import_commands`


<br>
## Give Apache appropriate permissions ##

<br>

`chown -R apache:apache /opt/pycloudportal`\
`chown -R apache:apache /opt/venvpycloud`\
`chown -R apache:apache /var/log/pyvcloud`\
`chown -R apache:apache /srv/isodiskmount/isodir`

<br>

# APACHE SETUP #

<pre> copy file django.conf into /etc/httpd/conf.d/ </pre>

## mod_wsgi ##
<pre> https://pypi.org/project/mod-wsgi/
Run the command:

                mod_wsgi-express install-module

This will copy the mod_wsgi module that was installed out of our virtual environment and into the apache specific folders. This way if we lose the venv, we dont lose the mod_wsgi module.
The command will output something like

                LoadModule wsgi_module modules/mod_wsgi-py27.so
                WSGIPythonHome /usr/local/lib

Take the LoadModule line and copy it into

                /etc/httpd/conf.modules.d/10-wsgi.conf

comment out the LoadModule line that already exists for the wsgi_module and replace it with the output of the mod_wsgi-express command

 </pre>


# Start Webserver #
`sudo service httpd restart`

## Logs are available in ##
<pre>
        /var/log/httpd/{error,access}.log
        /var/log/pycloud/pyvcloud_project.log
</pre>

## Cron Job Setup using Django-cron ##

### Overview ###

In this project, we utilize Django-cron to automate periodic tasks within the Django framework. Django-cron allows us to schedule specific tasks at different intervals, providing a flexible and Django-native solution for managing scheduled jobs.

### Django-cron Configuration ###

In the `settings.py` file, we've configured Django-cron to schedule various tasks using the `CRONJOBS` setting. The `CRONJOBS` list defines the timing and commands for each scheduled job. .
Here's an example:

# Runs Django management command to import the database at 1 AM every day.   
# Downloads historical reports for Datacenters at 2 AM every day.
# Downloads historical reports for Vapps at 2 AM every day.

```python
CRONJOBS = [
        ('0 1 * * *', 'django.core.management.call_command', ['import_database']), 
        ('0 2 * * *', 'pyvcloud_project.historical_report_cron_jobs.DatacenterReportDownloadCronJob'),
        ('0 2 * * *', 'pyvcloud_project.historical_report_cron_jobs.VappReportDownloadCronJob'),
]
```
### Managing Scheduled Jobs ###
To add all defined jobs from `CRONJOBS` to the crontab of the user running the command, use the following:

```bash
python manage.py crontab add
```

# To show the current active jobs for this project, use:
```bash 
python manage.py crontab show
```

# To remove all defined jobs, use:
```bash
python manage.py crontab remove
```

#### Cron Job Error ####
If you notice the message "You have new mail in /var/spool/mail/root," it indicates that the cron job generated output or encountered an issue. Review the contents of the /var/spool/mail/root file for additional information or error messages.