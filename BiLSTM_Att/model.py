# @Time    : 2020/2/8 16:59
# @Author  : R.Jian
# @NOTE    : 


import tracemalloc
import tensorflow as tf

import sys
sys.path.append(r"/home/tech/myPthonProject/MineNER/")
import BiLSTM_Att.setting_all as setting
from preprogram_of_CCKS2019_subtask1.pre_out import OutDataset
import preprogram_of_CCKS2019_subtask1.setting as p_setting
from BiLSTM_Att.layers import Attention

class Model(tf.keras.Model):
    def __init__(self):
        super(Model,self).__init__()
        LSTM_1 = tf.keras.layers.LSTM(setting.LISM_1_UNTIS,return_sequences=True)
        self.BiLSTM_1 = tf.keras.layers.Bidirectional(LSTM_1,merge_mode="concat")
        LSTM_2 = tf.keras.layers.LSTM(setting.LISM_1_UNTIS, return_sequences=True)
        self.BiLSTM_2 = tf.keras.layers.Bidirectional(LSTM_2, merge_mode="concat")
        LSTM_3 = tf.keras.layers.LSTM(setting.LISM_1_UNTIS, return_sequences=True)
        self.BiLSTM_3 = tf.keras.layers.Bidirectional(LSTM_3, merge_mode="concat")
        self.Att = Attention(units=p_setting.LABEL_SUM,trainable=True)

    @tf.function
    def call(self, inputs, training=None, mask=None):
        outs_1 = self.BiLSTM_1(inputs,mask=mask)
        outs = self.Att(outs_1,isfinal=False)
        inputs = tf.concat((outs_1,outs),axis=-1)
        outs_2 = self.BiLSTM_2(inputs,mask=mask)
        outs = self.Att(outs_2,isfinal=False)
        inputs = tf.concat((outs_2,outs),axis=-1)
        outs_3 = self.BiLSTM_3(inputs,mask=mask)
        outs = self.Att(outs_3,isfinal=True)
        return outs

    def loss(self,outs,y):
        "计算损失函数"
        outs = tf.math.log(outs)
        outs = tf.math.multiply(outs,y)
        loss = tf.math.reduce_sum(outs)
        return -loss

    @tf.function
    def pretect(self,outs):
        "测试需要的操作,只能一条，一条的输入"
        outs = tf.reshape(outs,[outs.shape[1],outs.shape[2]])
        pre_label = tf.math.argmax(outs,axis=1,output_type=tf.int32)
        return pre_label

    def calculate_num(self,pre,rel,sum):
        "每一次预测，统计其相关的信"
        list_pre = pre.numpy()[:sum.numpy()[0]]
        list_rel = rel.numpy()[:sum.numpy()[0]]
        rel,pre,corr = 0,0,0
        for i in range(sum.numpy()[0]):
            if list_rel[i] != 0:
                rel = rel + 1
            if list_pre[i] != 0:
                pre = pre + 1
            if (list_rel[i] == list_pre[i]) and (list_rel[i]!=0):
                corr = corr + 1
        return pre,rel,corr


    def check_F1(self,pre,rel,corr):
        "计算测评"
        precision = corr/pre
        recall = corr/rel
        f1 = (2*precision*recall)/(precision+recall+0.000001)
        return precision,recall,f1


@tf.function
def train(model,data,optimizer):
        with tf.GradientTape() as tape:
            out = model(data[0][0],mask=data[0][1])
            loss = model.loss(out,data[1][0])
        grad = tape.gradient(loss,model.trainable_variables)
        del tape
        optimizer.apply_gradients(zip(grad,model.trainable_variables))

@tf.function
def test(model,data):
    out = model(data[0][0], mask=data[0][1])
    return out

def fit(num,restore_path=None,epoch=setting.EPOCH):
    # num:存储的序号
    # restore_path:为载入模型的序号
    # epoch:为训练的次数
    outdataset = OutDataset(*setting.LOAD_NEW_PATH)
    outdataset_test = OutDataset(*setting.LOAD_TEST_PATH)
    outdataset_old = OutDataset(*setting.LOAD_OLD_PATH)
    bilstm_att = Model()
    op = tf.keras.optimizers.Adam(setting.LEARN_RATE)
    ckpt = tf.train.Checkpoint(model=bilstm_att)#在这个位置更新优化器操作。
    ckptmana = tf.train.CheckpointManager(ckpt,setting.MODEL_PATH_SAVE,max_to_keep=100,checkpoint_name=setting.MODEL_NAME_SAVE)
    if restore_path:
        ckpt.restore(setting.MODEL_PATH_RESTORE+setting.MODEL_NAME_RESTORE+restore_path)
    for _ in range(1,epoch+1):
        "修改前的训练"
        # for data in outdataset().batch(10):
        #     with tf.GradientTape() as tape:
        #         out = bilstm_att(data[0][0],mask=data[0][1])
        #         loss = bilstm_att.loss(out,data[1][0])
        #     grad = tape.gradient(loss,bilstm_att.trainable_variables)
        #     op.apply_gradients(zip(grad,bilstm_att.trainable_variables))
        "修改后的训练"
        for data in outdataset().shuffle(setting.BATCH_SIZE*setting.SHU_NUM,reshuffle_each_iteration=True).batch(setting.BATCH_SIZE):
            train(bilstm_att,data,op)

        if _ % setting.SAVED_EVERY_TIMES == 0:
            infor1 = "time = {} - save_num = {}  ;"
            infor2 = " train_new - precison={} - recall={} - F1={} ;"
            # infor3 = " train_old - precison={} - recall={} - F1={} ;"
            infor4 = " test - precison={} - recall={} - F1={}"

            "验证部分：将训练集的结果放到指定的文件中,验证  选中训练集。"
            pre,rel,corr = 1, 0, 0
            for data in outdataset().batch(1):
                out = bilstm_att(data[0][0],mask=data[0][1])
                pre_result = bilstm_att.pretect(out)
                rel_result = bilstm_att.pretect(data[1][0])
                list_result = bilstm_att.calculate_num(pre_result,rel_result,data[0][2])
                rel = rel + list_result[1]
                pre = pre + list_result[0]
                corr = corr +list_result[2]
            list_result = bilstm_att.check_F1(pre,rel,corr)
            infor1 =  infor1.format(_,num)
            infor2 =  infor2.format(*list_result)

            "验证部分：将训练集的结果放到指定的文件中,验证  未选中训练集。"
            """
            pre,rel,corr = 1, 0, 0
            for data in outdataset_old().batch(1):
                out = bilstm_att(data[0][0],mask=data[0][1])
                pre_result = bilstm_att.pretect(out)
                rel_result = bilstm_att.pretect(data[1][0])
                list_result = bilstm_att.calculate_num(pre_result,rel_result,data[0][2])
                rel = rel + list_result[1]
                pre = pre + list_result[0]
                corr = corr +list_result[2]
            list_result = bilstm_att.check_F1(pre,rel,corr)
            infor3.format(*list_result)
            """
            "验证部分：将训练集的结果放到指定的文件中,验证  测试集。"
            pre,rel,corr = 1, 0, 0
            for data in outdataset_test().batch(1):
                out = bilstm_att(data[0][0],mask=data[0][1])
                pre_result = bilstm_att.pretect(out)
                rel_result = bilstm_att.pretect(data[1][0])
                list_result = bilstm_att.calculate_num(pre_result,rel_result,data[0][2])
                rel = rel + list_result[1]
                pre = pre + list_result[0]
                corr = corr +list_result[2]
            list_result = bilstm_att.check_F1(pre,rel,corr)
            infor4 =  infor4.format(*list_result)

            "结果打到log文件中"
            f = open(setting.LOG_PATH,"a+",encoding="utf8")
            print(infor1+infor2+infor4,file=f)
            f.close()

            "模型的存储"
            ckptmana.save(num)
            num = num + 1
            if list_result[2]>0.95:
                break
        print("time ",_," finished")





# def test(restore_path):
#     # restore_path:要载入的文件路径
#     path = setting.MODEL_PATH_RESTORE+setting.MODEL_NAME_RESTORE+restore_path
#     outdataset = OutDataset(*setting.LOAD_PATH)
#     bilstm_att = Model()
#     op = tf.keras.optimizers.Adam(1e-5)
#     ckpt = tf.train.Checkpoint(model=bilstm_att,optimizer=op)
#     ckpt.restore(path)
#     for data in outdataset().batch(1).take(1):
#         out = bilstm_att(data[0][0], mask=data[0][1])
#         # 可以修改的部分。
#         result = bilstm_att.pretect(out)
#         print(" ".join([str(i) for i in result.numpy().tolist()]))


if __name__ == "__main__":
    "训练"
    fit(setting.STRAT_NUM,setting.MODEL_NUM_RESTORE)
    "测试"
    # test("-2")
