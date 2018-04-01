import argparse
import utils
import json
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, jsonify
import sync
import mine

app = Flask(__name__)

mongo_conn = utils.MongoDBWrapper()
sched = BackgroundScheduler(standalone=True)

import logging

logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.INFO)

@app.route('/')
def index():
    data = {
        'version': 'v1',
        'description': 'KMA Blockchain'
    }
    return jsonify(data), 200

@app.route('/new', methods=['POST'])
def new():
    data = request.get_json()
    # check required field
    required = ['author', 'title', 'doc_hash', 's3_url']
    if not all(k in data for k in required):
        return jsonify({'result': 'Missing values'}), 400
    # TODO
    # check doc_hash
    # if doc_hash already in blockchain database
    # return Document was exist and txid
    # push transaction to mongodb
    txid = mongo_conn.new_pending_transaction(data)
    
    return jsonify({'message': 'New transaction was submitted'\
                               ' to blockchain database',
                    'transaction_id': txid}), 201


#@app.route('upload', methods=['POST'])

@app.route('/pending-transactions')
def pending_transactions():
    """
    get all pending transactions for miner node
    """
    data = mongo_conn.query_pending_transactions()
    # import ipdb;ipdb.set_trace()
    return jsonify({'pending': data }), 200


@app.route('/mined', methods=["POST"])
def mined():
    """
    this endpoint to other node broadcast result
    """
    possible_block_dict = request.get_json()
    sched.add_job(mine.validate_possible_block,
                  args=[sched, mongo_conn, possible_block_dict],
                  id='validate_possible_block')
    return jsonify(received=True)


@app.route('/node-register', methods=['POST'])
def node_register():
    """
    register new node
    param: is_confirm, True if the node perform verify transactions
    """
    node = request.get_json()
    # check required fields
    required = ['node_address', 'node_port', 'is_confirm']
    if not all(k in node for k in required):
        return jsonify({'result': 'Missing values'}), 400

    node_uuid = mongo_conn.register_node(node)
    return jsonify({'node_uuid': node_uuid,
                    'message': 'New node was added to '\
                    'blockchain network'}), 201

@app.route('/confirm-nodes', methods=['GET'])
def confirm_nodes():
    """
    Get all confirm node in blockchain network
    """
    data = mongo_conn.query_confirm_node()
    return jsonify({'nodes': data}), 200


@app.route('/blockchain')
def blockchain():
    """
    return all blockchain data
    """
    local_chain = sync.sync_local()
    json_blocks = local_chain.block_list_to_dict()
    return jsonify(json_blocks)

if __name__ == '__main__':
    #args!
    parser = argparse.ArgumentParser(description='KMA Blockchain Node')
    parser.add_argument('--port', '-p', default=5000,
                        help='what port we will run the node on')
    args = parser.parse_args()
    # sync interval
    # sched.add_job(
    #     sync.sync_transactions,
    #     'interval',
    #     seconds=10,
    #     id='sync-transactions'
    # )
    # sched.add_job(
    #     sync.sync_node,
    #     'interval',
    #     seconds=10,
    #     id='sync-nodes'
    # )
    # sched.add_job(
    #     sync.sync_overall,
    #     'interval',
    #     seconds=30,
    #     id='sync-peer'
    # )
    sched.add_job(
        mine.mine_for_block,
        'interval',
        args=[sched, mongo_conn],
        seconds=30,
        id='mining-listener'
    )
    sched.start()
    app.run(debug=False,
            host='0.0.0.0',
            port=int(args.port))