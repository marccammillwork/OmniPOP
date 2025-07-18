const express = require('express');
const app = express();
const port = process.env.PORT || 5000;

app.get('/', (req, res) => {
  res.send('Hello from OmniPOP backend!');
});

app.listen(port, () => {
  console.log(`Backend listening on port ${port}`);
});
