import { useState, useEffect } from 'react';

export const GrabData = () => { // Async keyword will allow use of await command
    const [jsonData, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    useEffect(() => {
        const fetchData = async () => {
            try {
                const signed_tickets = await fetch('/api/s3-signer');
                
                if(!signed_tickets.ok) 
                    throw new Error('Could not fetch signed tickets.');

                const signed_tickets_json = await signed_tickets.json();

                console.log("API Structure: ", signed_tickets_json);

                const signed_urls = signed_tickets_json.signedURLs
                
                
                console.log('Obtained signed urls...');

                const signed_data_res = signed_urls.map(url => fetch(url));
                const signed_data = await Promise.all(signed_data_res);

                // Getting data
                const signed_data_json = signed_data.map(surl => {
                    if(!surl.ok) {
                        throw new Error(`AWS refused file ${surl.statusText}`)
                    }
                    return surl.json();
                })

                const jsonList = await Promise.all(signed_data_json);
                const finalData = jsonList.flat();

                console.log('Data obtained: ', finalData);

                setData(finalData);

                                
            } catch(error) {
                console.error('Error while fetching data', error);
                setError(error.message);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [])
 
    return { jsonData, loading, error };

}