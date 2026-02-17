from flask import render_template, url_for, request, redirect, send_from_directory,session,jsonify
from markupsafe import escape
from models import Student,Task,Project,Supervisor,Notification
from werkzeug.utils import secure_filename
import os
from datetime import datetime

def register_routes(app,db):
    @app.route("/")
    def home():
        if "name" in session.keys() :
            name = session["name"]
        else : name = "Friend"
        return render_template("home.html",name=name)

    @app.route('/logout')
    def logout():
        session.clear()
        # session['logged'] = False
        return redirect('/')
        
    @app.route("/account/<id>")
    def account(id):
        if 'logged' in session.keys(): 
            if id == 'me':
                name = session['name']
                phone = session['phone']
                specialties = session['specialties']
                email = session['email']
                department = session['department']
                year = session['year']
                in_team = session['in_team']
                project_id = session['project_id']
                image = session['image'] if 'image' in session.keys() else '/static/uploads/my_photo.jpg'
                return render_template('account.html',authorized=True,specialties=specialties, phone=phone, name=name, email=email, year=year, department=department, project_id=project_id, in_team=in_team, image=image)
            else :
                student = Student.query.get_or_404(id)
                name = student.name
                department = student.department
                year = student.year
                in_team = student.in_team
                image = student.image if student.image else '/static/uploads/my_photo.jpg' 
                specialties = student.specialties
                project_id = student.project_id
                phone = student.phone
                email = student.email
                return render_template('account.html',authorized=False,specialties=specialties, phone=phone, name=name, email=email, year=year, department=department, project_id=project_id, in_team=in_team, image=image)
        else :
            return redirect('/sign-in')
    @app.route('/edit/user/data', methods=['POST','GET'])
    def edit_user_data():
        if 'logged' in session.keys() :
            if request.method == 'GET':
                name = session['name']
                phone = session['phone']
                specialties = session['specialties']
                department = session['department']
                year = session['year']
                email = session['email']
                password = session['password']
                return render_template('edit_info.html',name=name, phone=phone, email=email, password=password, specialties=specialties)
            elif request.method == 'POST':
                name = request.form.get('name')
                phone = request.form.get('phone')
                email = request.form.get('email')
                year = request.form.get('year')
                department = request.form.get('department')
                specialties = request.form.get('specialties')
                password = request.form.get('password')

                p = Student.query.get_or_404(session['pid'])

                if Student.query.filter_by(email=email).count() > 0 and  p.email != email:
                    return render_template('edit_info.html', message="email already exist!") 

                session['name'] = name
                session['specialties'] = specialties
                session['phone'] = phone
                session['email'] = email
                session['department'] = department
                session['year'] = year
                session['password'] = password

                
                p.name = name 
                p.phone = phone
                p.email = email
                p.specialties = specialties
                p.year = year
                p.department = department
                p.password = password
                db.session.commit()

                return redirect('/account/me')
        else:
            return redirect('/sign-in')

    @app.route('/sign-up', methods=['POST','GET'])
    def sign_up():
        if request.method == 'GET' : 
            return render_template('sign_up.html')
        elif request.method == 'POST':
            name = request.form.get('name')
            phone = request.form.get('phone')
            email = request.form.get('email')
            specialties = request.form.get('specialties')
            year = request.form.get('year')
            department = request.form.get('department')
            password = request.form.get('password')
            if Student.query.filter_by(email=email).count()> 0 :
                    return render_template('sign_up.html', message="email already exist!")
            else :
                student = Student(name=name,specialties=specialties, phone=phone, email=email, department=department, year=year, password=password)
                db.session.add(student)
                db.session.commit()

            return redirect('/sign-in')

    @app.route('/sign-in', methods=['POST','GET'])
    def sign_in():
        if request.method == 'POST': 
            email = request.form['email']
            password = request.form['password']

            if Student.query.filter_by(email=email).count() > 0 :
                student = Student.query.filter_by(email=email).first()
                if student and student.password == password :
                    session['pid'] = student.pid
                    session['name'] = student.name
                    session['specialties'] = student.specialties
                    session['phone'] = student.phone
                    session['email'] = student.email
                    session['year'] = student.year
                    session['department'] = student.department
                    session['admin'] = student.admin
                    session['image'] = student.image
                    session['password'] = student.password
                    session['logged'] = True
                    session['project_id'] = student.project_id
                    session['in_team'] = student.in_team
                    return redirect('/')
                else :
                    return render_template('sign_in.html',message ="Wrong email or password!")
        elif request.method == 'GET':
            return render_template('sign_in.html')

    @app.route('/role')
    def choose_role():
        return render_template('roles.html')
    # ------------ uploading files -----------------
    ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif'}
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.',1)[1] in ALLOWED_EXTENSIONS

    @app.route('/upload', methods=['GET','POST'])
    def upload_file():
        if 'logged' in session.keys() :
            if request.method == 'GET':
                return render_template('upload_file.html')
            elif request.method == 'POST':
                file = request.files['file']
                if allowed_file(file.filename):
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))
                    img = Student.query.get_or_404(session['pid'])
                    img.image = f"/static/uploads/{file.filename}"
                    db.session.commit()
                    session['image'] = f"/static/uploads/{file.filename}"
                    return redirect(url_for('account')) # will cause error
                else :
                    return render_template('upload_file.html', message='Extension Is Not Allowed!')
        else:
            return redirect('/sign-in')

    # @app.route('/download_files') # remove this one
    # def download():
    #     files_list = os.listdir(app.config['UPLOAD_FOLDER'])
    #     return render_template('download.html',files=files_list)

    # @app.route('/download/<string:name>') # remove this one 
    # def downlaod_file(name):
    #     return send_from_directory(app.config['UPLOAD_FOLDER'],name)


    @app.route('/todo',methods=['GET','POST'])
    def todo():
        if 'logged' in session.keys() :
            if request.method == 'GET':
                tasks = Student.query.get(session['pid']).tasks
                return render_template('todo.html',tasks = tasks)
            elif request.method == 'POST':
                task = request.form.get('task')
                date = request.form.get('deadline')
                if not date : 
                    return "Please add a deadline",404 # decorate this
                deadline = datetime.strptime(date,"%Y-%m-%d").date() # converts html form date to python date object
                t = Task(description=task,student_id=session['pid'],deadline=deadline) # add project_id & assigned_to
                db.session.add(t)
                db.session.commit()
                return redirect('/todo')
        else:
                return redirect('/sign-in')

    @app.route('/change_status/<tid>',methods=['POST'])
    def change_status(tid):
        if 'logged' in session.keys() :
            task = Task.query.get(tid)
            task.status = "Done"
            db.session.commit()
            return redirect('/todo')
        else:
            return redirect('/sign-in')

    @app.route('/delete/task/<int:id>',methods=['POST'])
    def delete_task(id):
        if 'logged' in session.keys() :
            t = Task.query.get_or_404(id)
            db.session.delete(t)
            db.session.commit()
            return redirect('/todo')
        else:
            return redirect('/sign-in')

    @app.route('/friends')
    def friends():
        if 'logged' in session.keys() :
            friends = Student.query.all()
            return render_template('friends.html', users=friends, in_team=session['in_team'],my_id=session['pid'])
        else:
            return redirect('/sign-in')
    @app.route('/req_to_add/<int:id>',methods=['POST'])
    def req_to_add(id):
        new_notification = Notification(action='add',_from_id=session['pid'],_from_name=session['name'],student_id=id)
        db.session.add(new_notification)
        db.session.commit()
        return redirect('/friends')
    @app.route('/add_to_team/<int:id>',methods=['POST'])
    def add_to_team(id):
        new_member = Student.query.get_or_404(session['pid'])
        project_id = Student.query.get_or_404(id).project_id
        project = Project.query.get_or_404(project_id)
        members = project.get_members()
        members.append(session['pid'])
        project.set_members(members)
        new_member.in_team = True
        new_member.project_id = project_id
        session['project_id'] = project_id
        db.session.commit()
        return redirect(f'/project/{session['project_id']}')

    @app.route('/delete/user/<int:id>',methods=['POST'])
    def delete_student(id):
        if 'logged' in session.keys() :
            p = Student.query.get_or_404(id)
            db.session.delete(p)
            db.session.commit()
            return redirect('/friends')
        else:
            return redirect('/sign-in')

    # @app.route('/make_admin/<int:id>',methods=['GET']) # remove this (critical)
    # def make_admin(id):
    #     if 'logged' in session.keys() :
    #         p = Student.query.get_or_404(id)
    #         p.admin = True
    #         db.session.commit()
    #         return redirect('/friends')
    #     else:
    #             return redirect('/sign-in')
    @app.route('/new_project',methods=['POST','GET'])
    def new_project():
        if 'logged' in session.keys() :
            if request.method == 'GET':
                return render_template('new_project.html')
            else : 
                name = request.form.get('name')
                description = request.form.get('description')
                fields = []
                if request.form.get('AI') :
                    fields.append('AI')
                if request.form.get('Networking') :
                    fields.append('Network')
                if request.form.get('embedded') :
                    fields.append('Embedded')
                if request.form.get('web') :
                    fields.append('Web')
                if request.form.get('mobile') :
                    fields.append('Mobile')
                if request.form.get('cyber') :
                    fields.append('CyberSec')

                year = datetime.now().year
                project = Project(name=name, description=description, year=year,leader=session['pid'])
                project.set_fields(fields)
                db.session.add(project)
                db.session.commit()

                members = []
                members.append(session['pid'])
                project = Project.query.filter_by(description=description).first()
                project.set_members(members)
                project_id = project.pid
                student = Student.query.get_or_404(session['pid'])
                student.project_id = project_id
                student.in_team = True 
                session['in_team'] = True
                db.session.commit()

                return redirect('/projects')
        else:
            return redirect('/sign-in')
    @app.route('/projects')
    def projects():
        if 'logged' in session.keys():
            projects = Project.query.all()
            year = str(datetime.now().year)
            return render_template('projects.html',projects=projects,in_team = session['in_team'],this_year =year)
        else:
            return redirect('/sign-in')
    @app.route('/project/<id>')
    def project_detail(id):
        if 'logged' in session.keys():
            project = Project.query.get_or_404(id)
            members=project.get_members()
            members_name = []
            for member in members :
                members_name.append(f"{Student.query.get_or_404(member).name}")
            compined = zip(members_name, members)
            return render_template('project_details.html', project=project,fields=project.get_fields(),id=session['project_id'],compined=compined)
        else:
            return redirect('/sign-in')
    @app.route('/join/<int:id>',methods=['GET'])
    def join(id): # bug : reduntent join request
        if 'logged' in session.keys():
            project = Project.query.get(id)
            notification = Notification(action='join',_from_id=session['pid'],_from_name=session['name'],student_id=project.leader)
            db.session.add(notification)
            db.session.commit()
            return redirect('/projects')
        else:
            return redirect('/sign-in')

    # @app.route('/add_to_team')
    # def add_to_team():
    #     project = Project.query.get_or_404(session['project_id'])
    #     project.
    @app.route('/supervisor_signup',methods=['GET','POST'])
    def supervisor_signup(): # test for any empty data and different http methods
        if request.method == 'GET':
            return render_template('supervisor_signup.html')
        elif request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            specialties = request.form.get('specialties')
            role = request.form.get('role')
            department = request.form.get('department')
            password = request.form.get('password')

            if Supervisor.query.filter_by(email=email).count() > 0 :
                return render_template('sign_in.html',message='Email already exist!') 
            else :
                supervisor = Supervisor(name=name,email=email,phone=phone,specialties=specialties,department=department,role=role,password=password)
                db.session.add(supervisor)
                db.session.commit()

                return redirect('/supervisor_signin')
    @app.route('/supervisor_signin', methods=['POST','GET'])
    def supervisor_signin():
        if request.method == 'POST': 
            email = request.form['email']
            password = request.form['password']

            if Supervisor.query.filter_by(email=email).count() > 0 :
                supervisor = Supervisor.query.filter_by(email=email).first()
                if supervisor and supervisor.password == password :
                    session['did'] = supervisor.did
                    session['name'] = supervisor.name
                    session['specialties'] = supervisor.specialties
                    session['phone'] = supervisor.phone
                    session['email'] = supervisor.email
                    session['department'] = supervisor.department
                    session['password'] = supervisor.password
                    session['logged'] = True
                    session['projects'] = supervisor.projects
                    session['role'] = supervisor.role
                    return redirect('/')
                else :
                    return render_template('supervisor_signin.html',message ="Wrong email or password!")
        elif request.method == 'GET':
            return render_template('supervisor_signin.html')
    @app.route('/supervisors') # make the supervisors list only from same department 
    def supervisors():
        if 'logged' in session.keys():
            supervisors = Supervisor.query.all()
            return render_template('supervisors.html',supervisors=supervisors)
        else:
            return redirect('/sign-in')
    # ----------- Notifications ----------
    @app.route('/notifications')
    def notifications():
        if 'logged' in session.keys():
            student = Student.query.get_or_404(session['pid'])
            return render_template('notifications.html',notifications=student.notifications)
        else:
            return redirect('/sign-in')
    # -------------- APIs ----------------
    def is_allowed_api(): # change to better auth token
        header = request.headers.get("Authorization")
        if header and " Token " in header:
            token = header.rsplit(" ",1)[1]
            if token == "xxx":
                return True
            else : return False
        else : return False
    @app.route('/api/student/<int:id>')
    def student_api(id):
        if is_allowed_api():
            student = Student.query.get_or_404(id)
            return jsonify({
            "name":student.name,
            "specialties":student.specialties,
            "department":student.department,
            "grad_year":student.year,
            "image":student.image,
            "specialties_level":student.specialties_level,
            "in_team":student.in_team,
            "project_id":student.project_id
            })
        else :
            return jsonify({"error":"Not authenticated"})
    @app.route('/api/login',methods=['POST']) # Make input data JSON
    def api_login():
        email = request.form.get('email')
        password = request.form.get('password')
        if Student.query.filter_by(email=email).count() > 0 :
            student = Student.query.filter_by(email=email).first()
            if student and student.password == password :
                return jsonify({
                    "name":student.name,
                    "specialties":student.specialties,
                    "department":student.department,
                    "grad_year":student.year,
                    "image":student.image,
                    "in_team":student.in_team,
                    "project_id":student.project_id
                })
            else : return jsonify({"message":"Invalid credintials!!!!!1"})
        else : return jsonify({"message":"Invalid credintials!!!!!!2"})

    @app.route('/api/signup',methods=['POST']) # Make input data JSON
    def api_signup():
            name = request.form.get('name')
            phone = request.form.get('phone')
            email = request.form.get('email')
            specialties = request.form.get('specialties')
            year = request.form.get('year')
            department = request.form.get('department')
            password = request.form.get('password')
            if Student.query.filter_by(email=email).count()> 0 :
                    return jsonify({"message":"Email already exist!"})
            else :
                student = Student(name=name,specialties=specialties, phone=phone, email=email, department=department, year=year, password=password)
                db.session.add(student)
                db.session.commit()
                return jsonify({"message":"User registered successfully!"})