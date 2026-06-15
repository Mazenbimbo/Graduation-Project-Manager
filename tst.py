@app.route('/new_project',methods=['POST','GET'])
    def new_project():
        if 'logged' in session.keys() :
            if request.method == 'GET':
                if 'action' in request.args:
                    project = Project.query.get_or_404(session['project_id'])
                    return render_template('new_project.html',project=project)
                return render_template('new_project.html')
            else : 
                name = request.form.get('name')
                description = request.form.get('description')
                data = request.post(f'https://{domain}/api/check-similarity',json={"project_name":name,"description":description})
                res = data.json()
                if res['is_similar'] and res['is_similar']==True : 
                    return f"there is similar ideas and it is : {res["similar_projects"]}"

                similar_ideas = []
                for project in res["similar_projects"]
                    if project["score"] > 0.50:
                        similar_ideas.append(project["project"])


                available_fields = ['AI','Network','Embedded','Web','Cyber Security','Desktop','IT','Mobile']
                fields = []

                for field in available_fields : 
                    if request.form.get(field) :
                        fields.append(field)

                # edit ptoject (only student can edit)
                if 'action' in request.args:
                    p = Project.query.get_or_404(session['project_id'])
                    p.name =  request.form.get('name')
                    p.description = request.form.get('description')
                    p.set_fields(fields)
                    p.set_similar_ideas(similar_ideas)
                    db.session.commit()

                    flash('Edited successfully!','info')
                    return redirect(f'/project/{session['project_id']}')


                year = datetime.now().year
                project = Project(name=name, description=description, year=year,leader=session['pid'])
                project.set_fields(fields)
                project.set_similar_ideas(similar_ideas)
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

                return redirect('/ideas')
        else:
            return redirect('/sign-in')