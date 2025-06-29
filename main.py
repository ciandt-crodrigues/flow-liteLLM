from litellm.proxy.proxy_cli import run_server

from litellm.llms.vertex_ai.gemini import transformation

transformation._transform_request_body_old = transformation._transform_request_body

def flow_gemini_transform_request_body(**args):
    req = transformation._transform_request_body_old(**args)
    req['model'] = args['model'].removeprefix('gemini/')

    return req

transformation._transform_request_body = flow_gemini_transform_request_body

if __name__ == '__main__':
    run_server(["--config", "litellm-config.yml"])
