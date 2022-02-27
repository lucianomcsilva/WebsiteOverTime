// webhook.js
const crypto = require('crypto')
const express = require('express')
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
    // do something with message
    res.status(200).send('Ok')
  } catch (err) {
    console.error(err)
    res.status(500).send('server error sorry about that')
  }
}

app.post('/github-notification', (req, res, next) => {
    //TODO: trocar para variavel de ambiente
    const hmac = crypto.createHmac('sha256', 'RFy6kGY6_q@@XSU')
    hmac.update(JSON.stringify(req.body))
  
    // check has signature header and the decrypted signature matches
    if (req.get('X-Hub-Signature-256')) {
      if ( `sha256=${hmac.digest('hex').toString()}` === req.get('X-Hub-Signature-256') ){
        gitPull(local_repo, res)        
      } else {
        console.error("signature header received but hash did not match")
        res.status(403).send('Signature is missing or does not match')
      }
    } else {
      console.error('Signature missing')
      res.status(403).send('Signature is missing or does not match')
    }
})

// everything else should 404
app.use(function (req, res) {
  res.status(404).send("There's nothing here")
})

app.listen(port, () => {
  console.log(`Webhooks app listening on port ${port}`)
})