from app import app
from flask import render_template,flash,redirect,send_from_directory,url_for
from forms import LoginForm
from work import lookup_twitter_user,update_graph 
import os

pathToSave = ""

@app.route('/',methods = ['GET', 'POST'])
@app.route('/index',methods = ['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
	flag,user_id = lookup_twitter_user(form.screen_name.data)
	if flag:
		if os.path.exists(pathToSave+"data-"+str(user_id)+".csv"):
			return redirect(url_for('showGraph',userId = user_id))
		else:
			update_graph(user_id)
			flash('Come back to this link to get your graph:=blablabla:/showgraph/'+ str(user_id))
	else:
		flash('Bad Twitter name')
        return redirect(url_for('thanks'))
    return render_template('login.html', 
        form = form)

@app.route('/thanks')
def thanks():
	return render_template("thanks.html")

@app.route('/showgraph/<userId>')
def showGraph(userId):
		if os.path.exists(pathToSave + "data-"+userId+".csv"):
			return render_template('graph.html',id=userId)
		else:
			return "Wrong user id"

@app.route('/lookup/<userId>')
def lookup(userId):
	##TODO
