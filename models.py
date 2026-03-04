from app import db
import json

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
    tasks = db.relationship('Task',backref='student',lazy=True) # you can access 'student.tasks'
    notifications = db.relationship('Notification',backref='student',lazy=True)

    def __repr__(self):
        return f"name is : {self.name}"
        

class Task(db.Model):
    __tablename__ = 'task'
    tid = db.Column(db.Integer,primary_key=True)
    description = db.Column(db.Text(200), nullable=False)
    project_id = db.Column(db.Text(200), nullable=True)
    assigned_to = db.Column(db.Text(200))
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
    doctor = db.Column(db.Text(200))
    assistent = db.Column(db.Text(200))
    leader = db.Column(db.Integer,nullable=False)
    team_members = db.Column(db.Text(200))
    attachments = db.Column(db.Text(200))
    

    def set_attachments(self,attachments):
        self.attachments = json.dumps(attachments)

    def get_attachment(self):
        return json.loads(self.attachments)

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

    did = db.Column(db.Integer, primary_key=True,autoincrement=True)
    name = db.Column(db.Text(200), nullable=False)
    email = db.Column(db.Text(200), nullable=False)
    phone = db.Column(db.Text(200), nullable=False)
    specialties = db.Column(db.Text(200), nullable=False)
    department = db.Column(db.Text(10),nullable=True)
    role = db.Column(db.Text(10),nullable=False)
    projects = db.Column(db.Text(200),nullable=True)
    image = db.Column(db.Text,default='/static/uploads/user.png')
    password = db.Column(db.Text(200), nullable=False)
    notifications = db.relationship('Supervisor_notification',backref='supervisor',lazy=True)

    def __repr__(self):
        return f"Supervisor ID:{self.did}, name:{self.name}"    

class Notification(db.Model):
    __tablename__ = 'notification'

    nid = db.Column(db.Integer,primary_key=True)
    action = db.Column(db.String,nullable=False) # actions : add - join - supervise 
    _from_id = db.Column(db.Integer,nullable=True)
    _from_name = db.Column(db.String,nullable=True)
    student_id = db.Column(db.Integer,db.ForeignKey('person.pid'),nullable=False)

    def __repr__(self):
        return f"notification action: {self.action}"

class Supervisor_notification(db.Model):
    __tablename__ = 'supervisor_notification'
    nid = db.Column(db.Integer,primary_key=True)
    action = db.Column(db.String,nullable=False) # actions : supervise - 
    _from_id = db.Column(db.Integer,nullable=True)
    _from_name = db.Column(db.String,nullable=True)
    supervisor_id = db.Column(db.Integer,db.ForeignKey('supervisor.did'),nullable=False)

    def __repr__(self):
        return f'from {self._from_id}, action {self.action}'