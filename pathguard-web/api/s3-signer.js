import AWS from 'aws-sdk';
import dotenv from 'dotenv';
import path from 'path';
import fs from 'fs';

export default async function handler(req,res) {
    const currentFolder = process.cwd();

    const expectedPath = path.resolve(currentFolder, '.env.local');

    const fileExists = fs.existsSync(expectedPath);
    if(fileExists && process.env.NODE_ENV !== 'production') {
        await dotenv.config({path: expectedPath});
    }

    const filename = req.query.filename || 'markers_dat.json';

    try {
        const s3 = new AWS.S3({
            accessKeyId: process.env.AWS_KEY,
            secretAccessKey: process.env.SECRET_AWS_KEY,
            region: `ca-central-1`,
            signatureVersion: 'v4'
        });

        const listParams = {
            Bucket: process.env.BUCKET_NAME,
            Prefix: 'temp/'
        };
        const listObj = await s3.listObjectsV2(listParams).promise();
        
        if(!listObj.Contents || listObj.Contents.length === 0) {
            return res.status(200).json({ signedURLs: []});
        }

        const urlPromises = listObj.Contents
        .filter(file => file.Key.endsWith('.json'))
        .map(async (file) => {
            console.log(file);
            const signedURLParams = {
                Bucket: process.env.BUCKET_NAME,
                Key: file.Key,
                Expires: 60
            };
            return s3.getSignedUrlPromise('getObject',signedURLParams)
        })

        const signedURLs = await Promise.all(urlPromises);
        res.status(200).json({ signedURLs });
    } catch (error) {
        console.error("Backend Error: ", error);
        res.status(500).json({ error: 'Failed to generate URL'})
    }
}