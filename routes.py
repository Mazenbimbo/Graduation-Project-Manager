from flask import render_template, url_for, request, redirect, send_from_directory,session,jsonify,flash
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
            if id == 'me' or id == session['pid']:
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
                    flash("email already exist!","error")
                    return render_template('edit_info.html') 

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
            specialties = request.form.get('specialty')
            year = request.form.get('year')
            department = request.form.get('department')
            password = request.form.get('password')
            if Student.query.filter_by(email=email).count()> 0 :
                    flash("email already exist!","error")
                    return render_template('sign_up.html')
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
                    session['image'] = student.image
                    session['password'] = student.password
                    session['logged'] = True
                    session['project_id'] = student.project_id
                    session['in_team'] = student.in_team
                    if request.form.get('supervisor'):
                        session['role'] = 2
                    else : 
                        session['role'] = 3
                    return redirect('/')
                else :
                    flash("Wrong email or password!","error")
                    return render_template('sign_in.html')
            else :
                    flash("Wrong email or password!","error")
                    return render_template('sign_in.html')
        elif request.method == 'GET':
            return render_template('sign_in.html')

    @app.route('/role')
    def choose_role():
        return render_template('roles.html')
    # ------------ uploading files -----------------
    ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif','pdf'} 
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.',1)[1] in ALLOWED_EXTENSIONS

    @app.route('/upload/<string:_type>', methods=['GET','POST']) # implement full protection and consider error handling
    def upload_file(_type):
        if 'logged' in session.keys() :
            if request.method == 'GET':
                return render_template('upload_file.html')
            elif request.method == 'POST':
                file = request.files['file']
                if allowed_file(file.filename):
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))
                    if _type == "image" : 
                        img = Student.query.get_or_404(session['pid'])
                        img.image = f"/static/uploads/{file.filename}"
                        db.session.commit()
                        session['image'] = f"/static/uploads/{file.filename}"
                        return redirect(url_for('account')) # will cause error
                    elif _type == "attachment": 
                        my_project = Project.query.get_or_404(session['project_id'])
                        attachments = my_project.get_attachment()
                        attachments.append(f"/static/uploads/{file.filename}")
                        my_project.set_attachments(attachments)
                        db.session.commit()
                        return redirect(f'/project/{session["project_id"]}')
                else :
                    flash('Extension Is Not Allowed!','error')
                    return render_template('upload_file.html')
        else:
            return redirect('/sign-in')

    @app.route('/remove_attachment',methods=['POST'])
    def remove_attachment():
        file_path = request.form.get('file_path')
        full_file_path = app.config['PROJECT_DIR']+file_path
        if os.path.exists(full_file_path) : 
            os.remove(full_file_path)
            my_project = Project.query.get_or_404(session['project_id'])
            attachments = my_project.get_attachment()
            if file_path in attachments :
                attachments.remove(file_path)
                my_project.set_attachments(attachments)
                db.session.commit()
                return redirect(f'/project/{session["project_id"]}')
            else : 
                flash(f'{file_path} does not exist!')
                return redirect(f'/project/{session["project_id"]}')
        else : 
            flash(f'{file_path} does not exist!')
            return redirect(f'/project/{session["project_id"]}')

        
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
                    flash("Please add a deadline","error")
                    return redirect('/todo')
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

    @app.route('/friends') # AI Edited
    def friends():
        if 'logged' not in session:
            return redirect('/sign-in')

        specialty_filter = request.args.get('specialty', '').strip()
        not_in_team_only = request.args.get('not_in_team', '0') == '1'
        
        query = Student.query
        
        if specialty_filter:
            query = query.filter(Student.specialties == specialty_filter)
        
        if not_in_team_only:
            query = query.filter(Student.in_team == False)
        
        friends_list = query.all()
        
        # Get all distinct specialties for the dropdown ((( NEED TO UNDERSTAND THIS ONE BETTER)))
        specialties = db.session.query(Student.specialties).distinct().all()
        specialties = sorted([s[0] for s in specialties if s[0]])
        
        return render_template('friends.html',users=friends_list,in_team=session['in_team'],my_id=session['pid'],specialties=specialties,current_specialty=specialty_filter,not_in_team_checked=not_in_team_only)

    @app.route('/req_to_add/<int:id>',methods=['POST'])
    def req_to_add(id):
        if Notification.query.filter_by(action='add',_from_id=session['pid'],_from_name=session['name'],student_id=id).count()< 1:
            new_notification = Notification(action='add',_from_id=session['pid'],_from_name=session['name'],student_id=id)
            db.session.add(new_notification)
            db.session.commit()
            flash("Request sent!","info")
        else : 
            flash("Request already sent!","info")
        return redirect('/friends')
    @app.route('/add_to_team/<int:nid>/<int:id>/<string:action>',methods=['POST'])
    def add_to_team(nid, id, action): # accepting team leader req to join his team
        if action == 'accept' : 
            new_member = Student.query.get_or_404(session['pid'])
            project_id = Student.query.get_or_404(id).project_id
            project = Project.query.get_or_404(project_id)
            members = project.get_members()
            if len(members) < 6 : 
                members.append(session['pid'])
                project.set_members(members)
                new_member.in_team = True
                new_member.project_id = project_id
                session['project_id'] = project_id
            else :
                flash('Team is full!','error')
        deleted_notification = Notification.query.get_or_404(nid) 
        db.session.delete(deleted_notification)
        db.session.commit()
        if action == 'accept' :
            return redirect(f'/project/{session['project_id']}')
        else : 
            return redirect(f'/notifications')


    @app.route('/join/<int:id>',methods=['GET']) # req to join a team
    def join(id): # bug : reduntent join request
        if 'logged' in session.keys():
            project = Project.query.get(id)
            if Notification.query.filter_by(action='join',_from_id=session['pid'],_from_name=session['name'],student_id=project.leader).count()<1:
                notification = Notification(action='join',_from_id=session['pid'],_from_name=session['name'],student_id=project.leader)
                db.session.add(notification)
                db.session.commit()
                flash("Request sent!","info")
            else :
                flash("Request already sent","info")
            return redirect('/projects')
        else:
            return redirect('/sign-in')
            
    @app.route('/resp_join_req/<int:nid>/<int:from_id>/<string:action>',methods=['POST']) # team leader accepted join req
    def resp_join_req(nid, from_id, action):
        if action == 'accept':
            project = Project.query.get_or_404(session['project_id'])
            members = project.get_members()
            members.append(from_id)
            project.set_members(members)

            student = Student.query.get_or_404(from_id)
            student.in_team = True
            student.project_id = session['project_id']
        
        notification = Notification.query.get_or_404(nid)
        db.session.delete(notification)
        db.session.commit()
        return redirect('/notifications')

    @app.route('/delete/user/<int:id>',methods=['POST'])
    def delete_student(id):
        if 'logged' in session.keys() :
            p = Student.query.get_or_404(id)
            db.session.delete(p)
            db.session.commit()
            return redirect('/friends')
        else:
            return redirect('/sign-in')

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
                if not student.project_id : 
                    student.project_id = project_id
                    session['project_id'] = project_id
                else :
                    old_project = Project.query.get_or_404(student.project_id)
                    members = old_project.get_members()
                    if len(members) > 1 : 
                        old_project.leader = members[1]
                        members.remove(student.pid)
                        old_project.set_members(members)
                    else :
                        db.session.delete(old_project)
                    student.project_id = project_id
                    session['project_id'] = project_id
                student.in_team = True 
                session['in_team'] = True
                db.session.commit()

                return redirect('/projects')
        else:
            return redirect('/sign-in')
    
    @app.route('/exit_team',methods=['POST'])
    def exit_team():
        student = Student.query.get_or_404(session['pid'])
        old_project = Project.query.get_or_404(session['project_id'])
        members = old_project.get_members()
        if len(members) > 1 : 
            old_project.leader = members[1]
            members.remove(student.pid)
            old_project.set_members(members)
        else :
            db.session.delete(old_project)
        student.in_team = False
        student.project_id = None
        session['in_team'] = False
        session['project_id'] = None
        db.session.commit()
        return redirect('/projects')
    
    @app.route('/kick/<int:project_id>/<int:student_id>', methods=['POST'])
    def kick_member(project_id, student_id):
        if 'logged' not in session:
            return redirect('/sign-in')
        
        project = Project.query.get_or_404(project_id)
        student = Student.query.get_or_404(student_id)
        
        if session['pid'] != project.leader:
            flash('Only the team leader can remove members.', 'error')
            return redirect(url_for('project_detail', id=project_id))

        if student.pid == project.leader:
            flash('You cannot remove the team leader.', 'error')
            return redirect(url_for('project_detail', id=project_id))
        
        members = project.get_members()
        if student.pid in members:
            members.remove(student.pid)
            project.set_members(members)
        
        student.in_team = False
        student.project_id = None

        session['in_team'] = False
        session['project_id'] = None
        
        db.session.commit()
        flash(f'{student.name} has been removed from the team.', 'success')
        return redirect(url_for('project_detail', id=project_id))

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
            return render_template('project_details.html', project=project,fields=project.get_fields(),id=session['project_id'],compined=compined,attachments = project.get_attachment())
        else:
            return redirect('/sign-in')

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
                flash('Email already exist!','error')
                return render_template('sign_in.html') 
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
                    flash("Wrong email or password!","error")
                    return render_template('supervisor_signin.html')
        elif request.method == 'GET':
            return render_template('supervisor_signin.html')
    @app.route('/supervisors') # make the supervisors list only from same department 
    def supervisors():
        if 'logged' in session.keys():
            supervisors = Supervisor.query.all()
            return render_template('supervisors.html',supervisors=supervisors)
        else:
            return redirect('/sign-in')
    @app.route('/my_teams')
    def my_teams():
        return 'my teams'
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