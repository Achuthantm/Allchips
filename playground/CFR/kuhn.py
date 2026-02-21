import random
## Game State (card - Move1Move2)
## "", "b", "p", "pb"
MV = 2
class node:
    cm_regret = [0]*MV
    sum_strategy = [0]*MV
    def get_strategy(self):
        rsum = 0
        strat = [0]*MV
        for i in range(MV):
            if self.cm_regret[i] > 0:
                strat[i] = self.cm_regret[i]
                rsum += strat[i]
        if rsum <= 0:
            return [1.0/MV]*MV
        else:
            for i in range(MV):
                strat[i] = strat[i]/rsum
            return strat
    