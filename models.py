from app import db
import json

supervisor_project = db.Table(
    'supervisor_project',
    db.Column('supervisor_id', db.Integer, db.ForeignKey('supervisor.sid'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('project.pid'), primary_key=True)
)


class Student(db.Model):
    __tablename__ = 'person' 
    pid = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.Text, nullable = False)
    email = db.Column(db.Text)
    phone = db.Column(db.Text)
    specialties = db.Column(db.Text)
    password = db.Column(db.Text, nullable = False)
    project_id = db.Column(db.Integer,db.ForeignKey('project.pid'),nullable=True)
    in_team = db.Column(db.Boolean,default=False,nullable=False)
    year = db.Column(db.Integer,nullable=False)
    department = db.Column(db.Text,nullable=False)
    image = db.Column(db.Text,default='/static/uploads/user.png')
    tasks = db.relationship('Task',backref='student',lazy='dynamic') # you can access 'student.tasks'
    notifications = db.relationship('Notification',backref='student',lazy=True)

    @property
    def public_id(self):
        return f's{self.pid}'

    def __repr__(self):
        return f"name is : {self.name}"
        

class Task(db.Model):
    __tablename__ = 'task'
    tid = db.Column(db.Integer,primary_key=True)
    description = db.Column(db.Text(200), nullable=False)
    project_id = db.Column(db.Text(200), nullable=True)
    status = db.Column(db.Text(10),default="Not Done")
    deadline = db.Column(db.Date)
    student_id = db.Column(db.Integer,db.ForeignKey('person.pid'),nullable=False) # Task.student_id

    def __repr__(self):
        return f" Task : {self.description}"

class Project(db.Model):
    __tablename__ = 'project'
    pid = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.Text(200), nullable=False)
    description = db.Column(db.Text(200), nullable=False)
    year = db.Column(db.Text(200), nullable=False)
    fields = db.Column(db.Text)
    statue = db.Column(db.Text(200))
    doctor = db.Column(db.Integer, db.ForeignKey('supervisor.sid'), nullable=True)
    assistent = db.Column(db.Integer, db.ForeignKey('supervisor.sid'), nullable=True)
    leader = db.Column(db.Integer,nullable=False)
    team_members = db.Column(db.Text(200)) # old
    attachments = db.Column(db.Text(200))
    members = db.relationship('Student',backref='project',lazy='dynamic')
    
    @property
    def public_id(self):
        return f'p{self.pid}'

    def set_attachments(self,attachments):
        self.attachments = json.dumps(attachments)

    def get_attachment(self):
        return json.loads(self.attachments) if self.attachments else []

    def set_members(self,members):
        self.team_members = json.dumps(members)
    
    def get_members(self):
        return json.loads(self.team_members)

    def set_fields(self,fields_list): 
        self.fields = json.dumps(fields_list)

    def get_fields(self):
        return json.loads(self.fields)

    def __repr__(self):
        return f'project name : {self.name}!'

class Supervisor(db.Model):
    __tablename__ = 'supervisor'

    sid = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    image = db.Column(db.String(255),default='/static/uploads/user.png')   
    specialty = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(100), nullable=True)
    projects = db.relationship('Project',secondary=supervisor_project,backref=db.backref('supervisors', lazy='dynamic'),lazy='dynamic')
    # ^^ Many-to-many relationship, backref creates 'supervisors' on Project ^^
    notifications = db.relationship('Supervisor_notification',backref='supervisor',lazy=True)
    # add messages later

    @property
    def public_id(self):
        if self.role == 'Doctor':
            return f'd{self.sid}'
        return f'a{self.sid}'

    def __repr__(self):
        return f"Supervisor ID:{self.sid}, name:{self.name}"  
 


class Notification(db.Model):
    __tablename__ = 'notification'

    nid = db.Column(db.Integer,primary_key=True)
    action = db.Column(db.String,nullable=False) # actions : add - join - supervise 
    _from_id = db.Column(db.Integer,nullable=True)
    _from_name = db.Column(db.String,nullable=True)
    student_id = db.Column(db.Integer,db.ForeignKey('person.pid'),nullable=False)
    read = db.Column(db.Boolean,default=False,nullable=False)

    def __repr__(self):
        return f"notification action: {self.action}"

class Supervisor_notification(db.Model):
    __tablename__ = 'supervisor_notification'
    nid = db.Column(db.Integer,primary_key=True)
    action = db.Column(db.String,nullable=False) # actions : supervise - 
    _from_id = db.Column(db.Integer,nullable=True)
    _from_name = db.Column(db.String,nullable=True)
    supervisor_id = db.Column(db.Integer,db.ForeignKey('supervisor.sid'),nullable=False)
    read = db.Column(db.Boolean,default=False,nullable=False)

    def __repr__(self):
        return f'from {self._from_id}, action {self.action}'


class Meeting(db.Model):
    __tablename__ = 'meeting'
    mid = db.Column(db.Integer,primary_key=True)
    title = db.Column(db.Text(200))
    notes = db.Column(db.Text(200),nullable=True)
    date = db.Column(db.Date,nullable=False)
    time = db.Column(db.Time,nullable=False)
    place = db.Column(db.Text,nullable=False) # online or in_person
    link = db.Column(db.Text(200),nullable=True)
    project_id = db.Column(db.Integer,db.ForeignKey('project.pid'),nullable=False)
    project = db.relationship('Project',backref='meeting')