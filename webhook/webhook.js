// webhook.js
const crypto = require('crypto')
const express = require('express')
const fs = require("fs");
const port = 2999
const local_repo = "~/WebsiteOverTime"


const app = express()
app.use(express.json())

const util = require('util')
const exec = util.promisify(require('child_process').exec) // run child_process.exec as a Promise/async

async function gitPull(local_repo, res) {
  try {
    const { stdout, stderr } = await exec(`cd ${local_repo} && git pull`);
    let msg = stderr ? stderr : stdout // message is the error message if there is one, else the stdout
    compile()
    // do something with message    

    res.status(200).send('Ok')
  } catch (err) {
    console.error(err)
    res.status(500).send('server error sorry about that')
  }
}
async function compile(){
    const { stdout, stderr } = await exec(`pip install -r requirements.txt`);
    let msg = stderr ? stderr : stdout // message is the error message if there is one, else the stdout
    return msg
}
app.post('/github-notification', (req, res, next) => {
    
    //TODO: trocar para variavel de ambiente
    const hmac = crypto.createHmac('sha256', 'RFy6kGY6_q@@XSU')
    hmac.update(JSON.stringify(req.body))
  
    // check has signature header and the decrypted signature matches
    if (req.get('X-Hub-Signature-256')) {
      if ( `sha256=${hmac.digest('hex').toString()}` === req.get('X-Hub-Signature-256') ){
        gitPull(local_repo, res)          
        console.log("github-notification aparentilly sucessfull")
        return
      } else {
        console.error("signature header received but hash did not match")
        res.status(403).send('Signature is missing or does not match')
      }
    } else {
      console.error('Signature missing')
      res.status(403).send('Signature is missing or does not match')
    }
    console.log("github-notification error")
})

//Thanks to https://codesource.io/creating-a-logging-middleware-in-expressjs/
const getActualRequestDurationInMilliseconds = start => {
    const NS_PER_SEC = 1e9; //  convert to nanoseconds
    const NS_TO_MS = 1e6; // convert to milliseconds
    const diff = process.hrtime(start);
    return (diff[0] * NS_PER_SEC + diff[1]) / NS_TO_MS;
  };

  let demoLogger = (req, res, next) => { //middleware function
    let current_datetime = new Date();
    let formatted_date =
      current_datetime.getFullYear() +
      "-" +
      (current_datetime.getMonth() + 1) +
      "-" +
      current_datetime.getDate() +
      " " +
      current_datetime.getHours() +
      ":" +
      current_datetime.getMinutes() +
      ":" +
      current_datetime.getSeconds();
    let method = req.method;
    let url = req.url;
    let status = res.statusCode;
    const start = process.hrtime();
    const durationInMilliseconds = getActualRequestDurationInMilliseconds(start);
    let log = `[${formatted_date}] ${method}:${url} ${status} ${durationInMilliseconds.toLocaleString()} ms`;
    console.log(log);
    fs.appendFile("request_logs.txt", log + "\n", err => {
      if (err) {
        console.log(err);
      }
    });
    next();
  };

app.use(demoLogger);

// everything else should 404
app.use(function (req, res) {
  res.status(404).send("There's nothing here")
  console.log("not found")
})

app.listen(port, () => {
  console.log(`Webhooks app listening on port ${port}`)
})


