require('dotenv').config();
const express = require('express');
const sql = require('mssql');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors());
app.use(express.static('public'));

// Single Database Configuration
const dbConfig = {
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    server: process.env.DB_SERVER,
    database: process.env.DB_NAME,
    options: {
        encrypt: false,
        trustServerCertificate: true
    }
};

// Initialize a shared connection pool
const poolPromise = new sql.ConnectionPool(dbConfig)
    .connect()
    .then(pool => {
        console.log('Connected to MSSQL Database');
        return pool;
    })
    .catch(err => console.log('Database Connection Failed! Bad Config: ', err));

// Middleware to extract OpenID user from Nginx Proxy Manager
app.use((req, res, next) => {
    req.staffUser = req.headers['x-forwarded-email'] || 'dev_staff@school.edu';
    next();
});

// 1. Get Student Info from Aeries STU table
app.get('/api/student/:id', async (req, res) => {
    try {
        const pool = await poolPromise;
        let result = await pool.request()
            .input('studentId', sql.Int, req.params.id)
            .query('SELECT ID, FN, LN FROM STU WHERE ID = @studentId AND DEL = 0');

        if (result.recordset.length > 0) {
            res.json(result.recordset[0]);
        } else {
            res.status(404).json({ error: 'Student not found' });
        }
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// 2. Process Checkout
app.post('/api/checkout', async (req, res) => {
    const { studentId, firstName, lastName, barcode, reason } = req.body;
    try {
        const pool = await poolPromise;
        await pool.request()
            .input('stuId', sql.Int, studentId)
            .input('fn', sql.VarChar, firstName)
            .input('ln', sql.VarChar, lastName)
            .input('barcode', sql.VarChar, barcode)
            .input('reason', sql.VarChar, reason)
            .input('staffUser', sql.VarChar, req.staffUser)
            .query(`
                INSERT INTO ItemTransactions
                (StudentID, StudentFirstName, StudentLastName, ItemBarcode, Reason, Status, CheckoutStaffUser)
                VALUES (@stuId, @fn, @ln, @barcode, @reason, 'CheckedOut', @staffUser)
            `);
        res.json({ success: true, message: 'Item checked out successfully.' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// 3. Process Checkin
app.post('/api/checkin', async (req, res) => {
    const { barcode } = req.body;
    try {
        const pool = await poolPromise;
        let result = await pool.request()
            .input('barcode', sql.VarChar, barcode)
            .input('staffUser', sql.VarChar, req.staffUser)
            .query(`
                UPDATE ItemTransactions
                SET Status = 'CheckedIn', CheckinDateTime = GETDATE(), CheckinStaffUser = @staffUser
                OUTPUT inserted.StudentFirstName, inserted.StudentLastName
                WHERE ItemBarcode = @barcode AND Status = 'CheckedOut'
            `);

        if (result.recordset.length > 0) {
            res.json({ success: true, student: result.recordset[0] });
        } else {
            res.status(404).json({ error: 'Item not found or already checked in.' });
        }
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.listen(3000, () => console.log('Server running on port 3000'));
